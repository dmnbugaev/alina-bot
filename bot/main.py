import asyncio

from aiogram import Bot

from bot.app import create_dispatcher, setup_logging
from bot.config import get_settings


async def run_polling() -> None:
    setup_logging()
    settings = get_settings()
    bot = Bot(token=settings.bot_token)
    dp = create_dispatcher()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_polling())
