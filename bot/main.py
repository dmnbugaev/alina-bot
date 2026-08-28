import asyncio
from contextlib import suppress

from aiogram import Bot

from bot.app import create_dispatcher, setup_logging
from bot.config import get_settings
from bot.services.factory import get_payment_worker
from bot.services.telegram_service import TelegramService


async def run_polling() -> None:
    setup_logging()
    settings = get_settings()
    bot = Bot(token=settings.bot_token)
    dp = create_dispatcher()
    worker_task: asyncio.Task[None] | None = None
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        if settings.auto_fulfillment_enabled or settings.reminders_enabled:
            worker = get_payment_worker()
            worker_task = asyncio.create_task(
                worker.run(TelegramService(bot, settings)),
                name="payment-worker",
            )
        await dp.start_polling(bot)
    finally:
        if worker_task:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_polling())
