import asyncio

from aiogram import Bot

from bot.app import create_dispatcher, setup_logging
from bot.config import get_settings


async def run_polling() -> None:
    setup_logging()
    settings = get_settings()
    bot = Bot(token=settings.bot_token)
    dp = create_dispatcher()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_polling())
