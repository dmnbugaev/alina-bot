import logging

from aiogram import Bot
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request

from bot.app import create_dispatcher, setup_logging
from bot.config import get_settings

setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()
bot = Bot(token=settings.bot_token)
dispatcher = create_dispatcher()
app = FastAPI(title="Telegram Bot Webhook")


@app.get("/")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
async def api_healthcheck() -> dict[str, str]:
    return {"status": "ok"}


async def handle_telegram_update(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if settings.telegram_webhook_secret and (
        x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"ok": True}


@app.post("/")
async def telegram_webhook_root(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    return await handle_telegram_update(request, x_telegram_bot_api_secret_token)


@app.post("/api/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    return await handle_telegram_update(request, x_telegram_bot_api_secret_token)
