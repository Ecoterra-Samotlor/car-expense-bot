# 8484453423:AAGuix91df-9IzLHaJGHyjJ7rDotmJDmWSQ
# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import TG_BOT_TOKEN
from handlers import start, cars, expenses, repairs  # ← благодаря __init__.py

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token="8484453423:AAGuix91df-9IzLHaJGHyjJ7rDotmJDmWSQ")
    dp = Dispatcher()

    dp.include_routers(repairs, expenses, cars, start)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())