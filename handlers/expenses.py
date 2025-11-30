from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import os
from pathlib import Path
from datetime import datetime
from database import Database

router = Router()
db = Database()
BASE_MEDIA_DIR = Path("media")

def ensure_media_dirs(user_id: int, vin: str):
    user_dir = BASE_MEDIA_DIR / str(user_id) / vin
    (user_dir / "receipts").mkdir(parents=True, exist_ok=True)
    (user_dir / "parts").mkdir(parents=True, exist_ok=True)
    return user_dir

class ExpenseForm(StatesGroup):
    select_car = State()
    amount = State()
    category = State()
    mileage = State()
    note = State()
    attach_receipt = State()
    attach_part = State()
    waiting_for_receipt = State()
    waiting_for_part = State()

@router.message(F.text == "/add_expense")
async def add_expense_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT license_plate, name, vin FROM cars WHERE user_id = %s", (user_id,))
    cars = cursor.fetchall()
    conn.close()

    if not cars:
        await message.answer("❌ У вас нет добавленных авто. Сначала добавьте авто: /add_car")
        return

    # Формируем список: "А123ВС777 (Toyota Camry)"
    car_list = [f"{row[0]} ({row[1]})" for row in cars]
    await state.update_data(cars=cars)  # сохраняем [(license, name, vin), ...]
    await state.set_state(ExpenseForm.select_car)
    await message.answer("Выберите авто:\n" + "\n".join(car_list))

@router.message(ExpenseForm.select_car)
async def process_select_car(message: Message, state: FSMContext):
    selected = message.text.strip()
    data = await state.get_data()
    cars = data["cars"]  # [(license, name, vin), ...]

    selected_car = None
    for license_plate, name, vin in cars:
        if selected == f"{license_plate} ({name})":
            selected_car = (license_plate, name, vin)
            break

    if not selected_car:
        await message.answer("❌ Выберите авто из списка выше.")
        return

    await state.update_data(vin=selected_car[2], license_plate=selected_car[0])
    await state.set_state(ExpenseForm.amount)
    await message.answer("Введите сумму расхода:")

@router.message(ExpenseForm.amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
        await state.update_data(amount=amount)
        await state.set_state(ExpenseForm.category)
        await message.answer("Категория (например: топливо, ремонт, страховка):")
    except ValueError:
        await message.answer("❌ Введите корректную сумму (например: 3500):")

@router.message(ExpenseForm.category)
async def process_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text.strip())
    await state.set_state(ExpenseForm.mileage)
    await message.answer("Укажите пробег (км):")

@router.message(ExpenseForm.mileage)
async def process_mileage(message: Message, state: FSMContext):
    try:
        mileage = int(message.text)
        await state.update_data(mileage=mileage)
        await state.set_state(ExpenseForm.note)
        await message.answer("Комментарий (или пропустите):")
    except ValueError:
        await message.answer("❌ Введите число (например: 125400):")

@router.message(ExpenseForm.note)
async def process_note(message: Message, state: FSMContext):
    await state.update_data(note=message.text.strip() or None)

    # Сохраняем расход БЕЗ фото
    data = await state.get_data()
    user_id = message.from_user.id
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (user_id, vin, amount, category, mileage, note)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, data["vin"], data["amount"], data["category"], data["mileage"], data["note"]))
    expense_id = cursor.lastrowid
    conn.close()

    await state.update_data(expense_id=expense_id)

    # Спрашиваем про чек
    await state.set_state(ExpenseForm.attach_receipt)
    await message.answer("Хотите прикрепить фото чека? Отправьте фото или напишите 'нет'.")

# ——— Обработка фото чека ———
@router.message(ExpenseForm.attach_receipt, F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext):
    await _save_photo(message, state, "receipt")

@router.message(ExpenseForm.attach_receipt)
async def skip_receipt(message: Message, state: FSMContext):
    if message.text.lower() in ("нет", "no", "н"):
        await state.update_data(receipt_saved=True)
        await _ask_for_part_photo(message, state)
    else:
        await message.answer("Отправьте фото чека или напишите 'нет'.")

# ——— Обработка фото запчасти ———
@router.message(ExpenseForm.attach_part, F.photo)
async def handle_part_photo(message: Message, state: FSMContext):
    await _save_photo(message, state, "part")

@router.message(ExpenseForm.attach_part)
async def skip_part(message: Message, state: FSMContext):
    if message.text.lower() in ("нет", "no", "н"):
        await message.answer("✅ Расход сохранён!")
        await state.clear()
    else:
        await message.answer("Отправьте фото запчасти или напишите 'нет'.")

# ——— Вспомогательные функции ———
async def _save_photo(message: Message, state: FSMContext, photo_type: str):
    data = await state.get_data()
    user_id = message.from_user.id
    vin = data["vin"]
    expense_id = data["expense_id"]

    ensure_media_dirs(user_id, vin)
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{photo.file_id[:16]}.jpg"
    subdir = "receipts" if photo_type == "receipt" else "parts"
    filepath = BASE_MEDIA_DIR / str(user_id) / vin / subdir / filename

    await message.bot.download_file(file.file_path, filepath)

    # Обновляем БД
    conn = db.get_connection()
    cursor = conn.cursor()
    col = "receipt_path" if photo_type == "receipt" else "part_photo_path"
    cursor.execute(f"UPDATE expenses SET {col} = %s WHERE expense_id = %s", (str(filepath), expense_id))
    conn.close()

    await state.update_data(**{f"{photo_type}_saved": True})

    if photo_type == "receipt":
        await _ask_for_part_photo(message, state)
    else:
        await message.answer("✅ Расход сохранён!")
        await state.clear()

async def _ask_for_part_photo(message: Message, state: FSMContext):
    await state.set_state(ExpenseForm.attach_part)
    await message.answer("Хотите прикрепить фото запчасти? Отправьте фото или напишите 'нет'.")

# ——— Просмотр фото по авто ———
@router.message(F.text.startswith("/photos"))
async def send_photos(message: Message):
    user_id = message.from_user.id

    # Получаем список авто пользователя для выбора
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT license_plate, name, vin FROM cars WHERE user_id = %s", (user_id,))
    cars = cursor.fetchall()
    conn.close()

    if not cars:
        await message.answer("У вас нет авто.")
        return

    if len(message.text.split()) == 1:
        # Показываем список для выбора
        car_list = [f"{row[0]} ({row[1]})" for row in cars]
        await message.answer("Выберите авто:\n" + "\n".join(car_list) + "\n\nОтправьте ГОСНОМЕР из списка.")
        return

    # Пользователь прислал госномер
    license_input = message.text.split(maxsplit=1)[1].strip().upper()
    selected_vin = None
    for license_plate, name, vin in cars:
        if license_plate == license_input:
            selected_vin = vin
            break

    if not selected_vin:
        await message.answer("Авто с таким госномером не найдено.")
        return

    user_dir = BASE_MEDIA_DIR / str(user_id) / selected_vin
    if not user_dir.exists():
        await message.answer("Нет сохранённых фото для этого авто.")
        return

    sent = False
    for f in (user_dir / "receipts").glob("*.jpg"):
        await message.answer_photo(FSInputFile(f))
        sent = True
    for f in (user_dir / "parts").glob("*.jpg"):
        await message.answer_photo(FSInputFile(f))
        sent = True

    if not sent:
        await message.answer("Нет сохранённых фото.")