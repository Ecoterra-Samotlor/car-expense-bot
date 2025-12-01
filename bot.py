from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from database import Database

router = Router()  # ✅ Обязательно до использования @router
db = Database()

@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO users (user_id, username) VALUES (%s, %s)", (user_id, username))
    conn.close()

    # Главное меню
    kb = [
        ["🚗 Добавить авто"],
        ["💰 Добавить расход", "🔧 Добавить ремонт"],
        ["📊 Посмотреть расходы", "📸 Посмотреть фото"]
    ]
    await message.answer(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )