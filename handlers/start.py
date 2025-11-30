from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from database import Database

router = Router()
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

    await message.answer(
        "🚗 Добро пожаловать!\n"
        "/add_car — добавить авто\n"
        "/add_expense — добавить расход\n"
        "/photos — посмотреть фото по авто"
    )