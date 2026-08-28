import logging

from aiogram import Dispatcher

from bot.handlers import admin, payment, start


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(payment.router)
    dp.include_router(admin.router)
    return dp
