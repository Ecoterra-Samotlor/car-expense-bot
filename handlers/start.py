from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    # ... (регистрация пользователя)

    kb = [
        ["🚗 Добавить авто"],
        ["💰 Добавить расход", "🔧 Добавить ремонт"],
        ["📊 Посмотреть расходы", "📸 Посмотреть фото"]
    ]
    await message.answer(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )