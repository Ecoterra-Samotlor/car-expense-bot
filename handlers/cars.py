# handlers/cars.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import Database
from utils.validators import is_valid_vin, parse_date

router = Router()
db = Database()

class CarForm(StatesGroup):
    vin = State()
    name = State()
    license_plate = State()
    owner = State()
    insurance_expiry = State()
    inspection_expiry = State()

@router.message(F.text == "🚗 Добавить авто")
async def add_car_start(message: Message, state: FSMContext):
    await state.set_state(CarForm.vin)
    await message.answer("Введите VIN (17 символов):")

@router.message(CarForm.vin)
async def process_vin(message: Message, state: FSMContext):
    vin = message.text.strip().upper()
    if not is_valid_vin(vin):
        await message.answer("❌ Неверный VIN. Должно быть 17 символов (без I/O/Q). Попробуйте снова:")
        return
    await state.update_data(vin=vin)
    await state.set_state(CarForm.name)
    await message.answer("Введите название авто (например, Toyota Camry):")

@router.message(CarForm.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(CarForm.license_plate)
    await message.answer("Введите госномер (обязательно, например: А123ВС777):")

@router.message(CarForm.license_plate)
async def process_license(message: Message, state: FSMContext):
    license_plate = message.text.strip().upper()
    if not license_plate:
        await message.answer("Госномер обязателен. Попробуйте снова:")
        return
    # Проверим, не занят ли госномер у этого пользователя
    user_id = message.from_user.id
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM cars WHERE user_id = %s AND license_plate = %s", (user_id, license_plate))
    if cursor.fetchone():
        conn.close()
        await message.answer("❌ Этот госномер уже используется у вас. Введите другой:")
        return
    conn.close()

    await state.update_data(license_plate=license_plate)
    await state.set_state(CarForm.owner)
    await message.answer("Укажите собственника:")

@router.message(CarForm.owner)
async def process_owner(message: Message, state: FSMContext):
    await state.update_data(owner=message.text.strip())
    await state.set_state(CarForm.insurance_expiry)
    await message.answer("Дата окончания страховки (ДД.ММ.ГГГГ):")

@router.message(CarForm.insurance_expiry)
async def process_insurance(message: Message, state: FSMContext):
    date_val = parse_date(message.text)
    if not date_val:
        await message.answer("❌ Неверный формат. Введите: 15.06.2026")
        return
    await state.update_data(insurance_expiry=date_val)
    await state.set_state(CarForm.inspection_expiry)
    await message.answer("Дата окончания техосмотра (ДД.ММ.ГГГГ):")

@router.message(CarForm.inspection_expiry)
async def process_inspection(message: Message, state: FSMContext):
    date_val = parse_date(message.text)
    if not date_val:
        await message.answer("❌ Неверный формат. Введите: 15.06.2026")
        return

    data = await state.get_data()
    user_id = message.from_user.id

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO cars (vin, user_id, name, license_plate, owner, insurance_expiry, inspection_expiry)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data['vin'], user_id, data['name'], data['license_plate'],
            data['owner'], data['insurance_expiry'], date_val
        ))
        await message.answer(f"✅ Авто добавлено!\nГосномер: {data['license_plate']}\nVIN: {data['vin']}")
    except Exception as e:
        await message.answer("❌ Ошибка при сохранении. Возможно, VIN уже существует.")
        print(f"DB Error: {e}")
    finally:
        conn.close()
    await state.clear()