# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import TG_BOT_TOKEN  # ← убедись, что токен в .env

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TG_BOT_TOKEN)  # ← не вставляй токен в код!
    dp = Dispatcher()

    # Явно импортируем и подключаем роутеры
    from handlers.start import router as start_router
    from handlers.cars import router as cars_router
    from handlers.expenses import router as expenses_router
    from handlers.repairs import router as repairs_router

    dp.include_routers(repairs_router, expenses_router, cars_router, start_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())