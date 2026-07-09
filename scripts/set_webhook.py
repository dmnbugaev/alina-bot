import asyncio
import sys
from pathlib import Path

from aiogram import Bot

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.app import create_dispatcher
from bot.config import get_settings


async def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/set_webhook.py https://your-domain.vercel.app/api/webhook")
        raise SystemExit(2)

    webhook_url = sys.argv[1]
    settings = get_settings()
    dp = create_dispatcher()
    bot = Bot(settings.bot_token)

    try:
        await bot.set_webhook(
            webhook_url,
            secret_token=settings.telegram_webhook_secret,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
        print(f"webhook set: {webhook_url}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
