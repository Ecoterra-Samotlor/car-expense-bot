# handlers/repairs.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from pathlib import Path
import os
from datetime import datetime
from database import Database

router = Router()
db = Database()
BASE_MEDIA_DIR = Path("media")

class RepairForm(StatesGroup):
    select_car = State()
    mileage = State()
    total_amount = State()
    add_works = State()
    add_parts = State()
    add_parts_brand = State()      # ← ЭТО СОСТОЯНИЕ ОТСУТСТВУЕТ
    add_parts_amount = State()
    add_parts_photo = State()
    confirm = State()

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def ensure_repair_media_dir(user_id: int, vin: str, repair_id: int):
    path = BASE_MEDIA_DIR / str(user_id) / vin / "repairs" / str(repair_id) / "parts"
    path.mkdir(parents=True, exist_ok=True)
    return path

# ===== ОСНОВНЫЕ ХЕНДЛЕРЫ =====

@router.message(F.text == "🔧 Добавить ремонт")
async def add_repair_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT license_plate, name, vin FROM cars WHERE user_id = %s", (user_id,))
    cars = cursor.fetchall()
    conn.close()

    if not cars:
        await message.answer("❌ Сначала добавьте авто: /add_car")
        return

    car_list = [f"{row[0]} ({row[1]})" for row in cars]
    await state.update_data(cars=cars)
    await state.set_state(RepairForm.select_car)
    await message.answer("Выберите авто для ремонта:\n" + "\n".join(car_list))

@router.message(RepairForm.select_car)
async def process_repair_car(message: Message, state: FSMContext):
    # ... (аналогично expenses.py — выбор по госномеру)
    selected = message.text.strip()
    data = await state.get_data()
    cars = data["cars"]
    selected_car = None
    for license_plate, name, vin in cars:
        if selected == f"{license_plate} ({name})":
            selected_car = (license_plate, name, vin)
            break
    if not selected_car:
        await message.answer("Выберите авто из списка.")
        return
    await state.update_data(vin=selected_car[2])
    await state.set_state(RepairForm.mileage)
    await message.answer("Пробег на момент ремонта (км):")

@router.message(RepairForm.mileage)
async def process_mileage(message: Message, state: FSMContext):
    try:
        mileage = int(message.text)
        await state.update_data(mileage=mileage)
        await state.set_state(RepairForm.total_amount)
        await message.answer("Общая стоимость ремонта (или 0, если будем считать по позициям):")
    except ValueError:
        await message.answer("Введите число (пример: 125400)")

@router.message(RepairForm.total_amount)
async def process_total_amount(message: Message, state: FSMContext):
    try:
        total = float(message.text.replace(',', '.'))
        await state.update_data(total_amount=total, works=[], parts=[])
        await state.set_state(RepairForm.add_works)
        await message.answer(
            "Опишите работы (по одной за раз).\n"
            "Формат: <описание> - <сумма>\n"
            "Пример: Замена масла - 1500\n"
            "Когда закончите — напишите «готово»."
        )
    except ValueError:
        await message.answer("Введите сумму (пример: 8450)")

@router.message(RepairForm.add_works)
async def add_work(message: Message, state: FSMContext):
    if message.text.lower() in ("готово", "done", "готов"):
        await state.set_state(RepairForm.add_parts)
        await message.answer(
            "Добавьте запчасти.\n"
            "Присылайте по одной: сначала артикул, потом бренд, потом стоимость, потом фото.\n"
            "Или напишите «без запчастей»."
        )
        return

    try:
        desc, amt = message.text.split(" - ", 1)
        amount = float(amt.replace(',', '.'))
        data = await state.get_data()
        works = data.get("works", [])
        works.append({"description": desc.strip(), "amount": amount})
        await state.update_data(works=works)
        await message.answer("Работа добавлена. Ещё или «готово»?")
    except Exception:
        await message.answer("Формат: <описание> - <сумма>\nПример: Диагностика - 1000")

@router.message(RepairForm.add_parts)
async def add_part_step1(message: Message, state: FSMContext):
    if message.text.lower() in ("без запчастей", "нет", "н"):
        await _save_repair(message, state)
        return

    # Ожидаем артикул
    await state.update_data(current_part={"part_number": message.text.strip()})
    await state.set_state(RepairForm.add_parts_brand)
    await message.answer("Фирма-производитель:")

@router.message(RepairForm.add_parts_brand)
async def add_part_step2(message: Message, state: FSMContext):
    data = await state.get_data()
    part = data["current_part"]
    part["brand"] = message.text.strip()
    await state.update_data(current_part=part)
    await state.set_state(RepairForm.add_parts_amount)
    await message.answer("Стоимость запчасти:")

@router.message(RepairForm.add_parts_amount)
async def add_part_step3(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        data = await state.get_data()
        part = data["current_part"]
        part["amount"] = amount
        await state.update_data(current_part=part)
        await state.set_state(RepairForm.add_parts_photo)
        await message.answer("Пришлите фото запчасти или напишите «без фото».")
    except ValueError:
        await message.answer("Введите стоимость числом.")

@router.message(RepairForm.add_parts_photo, F.photo)
async def add_part_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    part = data["current_part"]
    user_id = message.from_user.id
    vin = data["vin"]

    # Создадим заглушку repair_id = 0 — заменим после INSERT
    temp_dir = ensure_repair_media_dir(user_id, vin, 0)
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    filename = f"part_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = temp_dir / filename
    await message.bot.download_file(file.file_path, filepath)

    part["photo_path"] = str(filepath)
    parts = data.get("parts", [])
    parts.append(part)
    await state.update_data(parts=parts, current_part=None)
    await state.set_state(RepairForm.add_parts)
    await message.answer("Запчасть добавлена. Ещё или «без запчастей»?")

@router.message(RepairForm.add_parts_photo)
async def skip_part_photo(message: Message, state: FSMContext):
    if message.text.lower() in ("без фото", "нет", "н"):
        data = await state.get_data()
        part = data["current_part"]
        part["photo_path"] = None
        parts = data.get("parts", [])
        parts.append(part)
        await state.update_data(parts=parts, current_part=None)
        await state.set_state(RepairForm.add_parts)
        await message.answer("Запчасть добавлена (без фото). Ещё или «без запчастей»?")
    else:
        await message.answer("Пришлите фото или напишите «без фото».")

# ===== СОХРАНЕНИЕ В БД =====

async def _save_repair(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    vin = data["vin"]
    mileage = data["mileage"]
    total = data["total_amount"]
    works = data.get("works", [])
    parts = data.get("parts", [])

    conn = db.get_connection()
    cursor = conn.cursor()

    # Вставляем ремонт
    cursor.execute("""
        INSERT INTO repairs (user_id, vin, mileage, total_amount, note)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, vin, mileage, total, "Ремонт через бота"))
    repair_id = cursor.lastrowid

    # Обновляем пути фото (заменяем repair_id=0 на реальный)
    for part in parts:
        if part.get("photo_path"):
            old_path = Path(part["photo_path"])
            new_dir = ensure_repair_media_dir(user_id, vin, repair_id)
            new_path = new_dir / old_path.name
            old_path.rename(new_path)
            part["photo_path"] = str(new_path)

    # Вставляем работы
    for work in works:
        cursor.execute("""
            INSERT INTO repair_works (repair_id, description, amount)
            VALUES (%s, %s, %s)
        """, (repair_id, work["description"], work["amount"]))

    # Вставляем запчасти
    for part in parts:
        cursor.execute("""
            INSERT INTO repair_parts (repair_id, part_number, brand, amount, photo_path)
            VALUES (%s, %s, %s, %s, %s)
        """, (repair_id, part["part_number"], part["brand"], part["amount"], part["photo_path"]))

    conn.close()
    await message.answer("✅ Ремонт сохранён!")
    await state.clear()

# ===== ПРОСМОТР РЕМОНТОВ =====

@router.message(F.text == "📊 Посмотреть расходы")
async def view_repairs_menu(message: Message):
    # Здесь будет меню: "Простые расходы" / "Ремонты"
    kb = [
        ["📊 Простые расходы", "🔧 История ремонтов"],
        ["↩️ Назад"]
    ]
    from aiogram.types import ReplyKeyboardMarkup
    await message.answer("Выберите тип:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@router.message(F.text == "🔧 История ремонтов")
async def list_repairs(message: Message):
    user_id = message.from_user.id
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.repair_id, r.mileage, r.total_amount, r.created_at, c.license_plate
        FROM repairs r
        JOIN cars c ON r.vin = c.vin
        WHERE r.user_id = %s
        ORDER BY r.created_at DESC
    """, (user_id,))
    repairs = cursor.fetchall()
    conn.close()

    if not repairs:
        await message.answer("Нет записей о ремонтах.")
        return

    # Создаём inline-кнопки с датой и суммой
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for rid, mileage, amount, created_at, license_plate in repairs:
        date_str = created_at.strftime("%d.%m.%Y")
        text = f"🔧 {license_plate} | {mileage} км | {amount} ₽ | {date_str}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"repair_{rid}")])

    await message.answer("Выберите ремонт:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("repair_"))
async def show_repair_details(callback: CallbackQuery):
    repair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    conn = db.get_connection()
    cursor = conn.cursor()

    # Основная info
    cursor.execute("""
        SELECT r.mileage, r.total_amount, r.created_at, c.license_plate, c.name
        FROM repairs r
        JOIN cars c ON r.vin = c.vin
        WHERE r.repair_id = %s AND r.user_id = %s
    """, (repair_id, user_id))
    main = cursor.fetchone()
    if not main:
        await callback.answer("Запись не найдена.")
        return

    mileage, total, created_at, license, name = main
    date_str = created_at.strftime("%d.%m.%Y")

    # Работы
    cursor.execute("SELECT description, amount FROM repair_works WHERE repair_id = %s", (repair_id,))
    works = cursor.fetchall()

    # Запчасти
    cursor.execute("SELECT part_number, brand, amount, photo_path FROM repair_parts WHERE repair_id = %s", (repair_id,))
    parts = cursor.fetchall()

    conn.close()

    # Формируем текст
    text = f"Дата: {date_str}\nПробег: {mileage} км\nАвто: {license} ({name})\n\n"

    if works:
        text += "Работы:\n"
        for desc, amt in works:
            text += f"- {desc} — {amt} ₽\n"
        text += "\n"

    if parts:
        text += "Запчасти:\n"
        for pn, brand, amt, _ in parts:
            text += f"- {pn} | {brand} | {amt} ₽\n"

    # Кнопка "показать фото"
    has_photos = any(p[3] for p in parts)
    kb = []
    if has_photos:
        kb = [[InlineKeyboardButton(text="📸 Показать фото запчастей", callback_data=f"repair_photos_{repair_id}")]]

    from aiogram.types import InlineKeyboardMarkup
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("repair_photos_"))
async def send_repair_photos(callback: CallbackQuery):
    repair_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT photo_path FROM repair_parts WHERE repair_id = %s AND photo_path IS NOT NULL", (repair_id,))
    photos = cursor.fetchall()
    conn.close()

    if not photos:
        await callback.message.answer("Нет фото.")
        return

    from aiogram.types import FSInputFile
    for (path,) in photos:
        if os.path.exists(path):
            await callback.message.answer_photo(FSInputFile(path))

    await callback.answer()