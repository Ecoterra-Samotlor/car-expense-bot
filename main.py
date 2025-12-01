# main.py
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# ✅ Подключаем ВСЕ роутеры из handlers
from handlers import start, cars, expenses, repairs

load_dotenv()
BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TG_BOT_TOKEN не найден в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ✅ Включаем роутеры в правильном порядке
dp.include_router(start.router)      # /start и главное меню
dp.include_router(cars.router)       # добавление авто
dp.include_router(expenses.router)   # расходы
dp.include_router(repairs.router)    # ремонты

async def main():
    print("✅ Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())