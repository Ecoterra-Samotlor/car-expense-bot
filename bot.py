from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from database import Database

router = Router()  # ✅ Обязательно до использования @router
db = Database()

@router.message(F.text == "/start")
@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO users (user_id, username) VALUES (%s, %s)", (user_id, username))
    conn.close()

    # ✅ Правильное создание клавиатуры в aiogram 3
    kb = [
        [KeyboardButton(text="🚗 Добавить авто")],
        [KeyboardButton(text="💰 Добавить расход"), KeyboardButton(text="🔧 Добавить ремонт")],
        [KeyboardButton(text="📊 Посмотреть расходы"), KeyboardButton(text="📸 Посмотреть фото")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer("Выберите действие:", reply_markup=markup)