import asyncio
import sys
from pathlib import Path

from aiogram import Bot

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import get_settings


async def main() -> None:
    settings = get_settings()
    bot = Bot(settings.bot_token)
    try:
        me = await bot.get_me()
        print("telegram get_me: ok")
        print(f"bot username: @{me.username}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
