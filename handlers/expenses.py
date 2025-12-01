# handlers/expenses.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import os
from aiogram.types import FSInputFile
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
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
    amount = State()
    category = State()
    mileage = State()
    note = State()
    attach_receipt = State()
    attach_part = State()
    vin = State()  # будем хранить VIN после выбора авто

@router.message(F.text == "💰 Добавить расход")
async def add_expense_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT license_plate, vin FROM cars WHERE user_id = %s", (user_id,))
    cars = cursor.fetchall()
    conn.close()

    if not cars:
        await message.answer("❌ У вас нет добавленных авто. Сначала добавьте авто: /add_car")
        return

    # Создаём inline-кнопки: одна кнопка — один госномер
    buttons = []
    for license_plate, vin in cars:
        buttons.append([InlineKeyboardButton(text=license_plate, callback_data=f"car_{vin}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите авто:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("car_"))
async def process_car_selection(callback: CallbackQuery, state: FSMContext):
    vin = callback.data.split("_", 1)[1]
    await state.update_data(vin=vin)
    await state.set_state(ExpenseForm.amount)
    await callback.message.edit_text("Введите сумму расхода:")
    await callback.answer()  # убирает "часики" на кнопке

# --- Дальше — те же шаги, но с учётом VIN из state ---
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

    data = await state.get_data()
    user_id = message.from_user.id
    vin = data["vin"]

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (user_id, vin, amount, category, mileage, note)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, vin, data["amount"], data["category"], data["mileage"], data["note"]))
    expense_id = cursor.lastrowid
    conn.close()

    await state.update_data(expense_id=expense_id)
    await state.set_state(ExpenseForm.attach_receipt)
    await message.answer("Хотите прикрепить фото чека? Отправьте фото или напишите 'нет'.")

# --- Остальное без изменений ---
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

    print(f"DEBUG: Saving photo to {filepath}")
    print(f"DEBUG: File exists after save: {filepath.exists()}")

async def _ask_for_part_photo(message: Message, state: FSMContext):
    await state.set_state(ExpenseForm.attach_part)
    await message.answer("Хотите прикрепить фото запчасти? Отправьте фото или напишите 'нет'.")

# --- Просмотр фото ---
@router.message(F.text == "📸 Посмотреть фото")
async def send_photos(message: Message):
    user_id = message.from_user.id

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT license_plate, vin FROM cars WHERE user_id = %s", (user_id,))
    cars = cursor.fetchall()
    conn.close()

    if not cars:
        await message.answer("У вас нет авто.")
        return

    buttons = []
    for license_plate, vin in cars:
        buttons.append([InlineKeyboardButton(text=license_plate, callback_data=f"photos_{vin}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите авто для просмотра фото:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("photos_"))
async def send_photos_for_vin(callback: CallbackQuery):
    vin = callback.data.split("_", 1)[1]
    user_id = callback.from_user.id
    user_dir = BASE_MEDIA_DIR / str(user_id) / vin

    if not user_dir.exists():
        await callback.message.answer("Нет сохранённых фото для этого авто.")
        await callback.answer()
        return

    sent = False
    for f in (user_dir / "receipts").glob("*.jpg"):
        await callback.message.answer_photo(FSInputFile(f))
        sent = True
    for f in (user_dir / "parts").glob("*.jpg"):
        await callback.message.answer_photo(FSInputFile(f))
        sent = True

    if not sent:
        await callback.message.answer("Нет сохранённых фото.")
    await callback.answer()