# main.py
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from handlers import start, cars, expenses, repairs  # ← эти имена — Router'ы

load_dotenv()
BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TG_BOT_TOKEN не найден в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Подключаем напрямую — они уже Router объекты
dp.include_router(start)
dp.include_router(cars)
dp.include_router(expenses)
dp.include_router(repairs)

async def main():
    print("✅ Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())