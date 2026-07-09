import logging
from asyncio import to_thread
from uuid import uuid4

from yookassa import Configuration, Payment

from bot.config import Settings

logger = logging.getLogger(__name__)


class YooKassaService:
    def __init__(self, settings: Settings):
        self.settings = settings
        Configuration.account_id = settings.yookassa_shop_id
        Configuration.secret_key = settings.yookassa_secret_key

    def create_payment(self, telegram_id: int) -> tuple[str, str]:
        payment = Payment.create(
            {
                "amount": {
                    "value": self.settings.payment_amount,
                    "currency": self.settings.payment_currency,
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": self.settings.yookassa_return_url,
                },
                "capture": True,
                "description": self.settings.payment_description,
                "metadata": {"telegram_id": str(telegram_id)},
            },
            str(uuid4()),
        )
        logger.info("Created YooKassa payment %s for telegram_id=%s", payment.id, telegram_id)
        return payment.id, payment.confirmation.confirmation_url

    async def create_payment_async(self, telegram_id: int) -> tuple[str, str]:
        return await to_thread(self.create_payment, telegram_id)

    def get_payment(self, payment_id: str):
        return Payment.find_one(payment_id)

    async def get_payment_async(self, payment_id: str):
        return await to_thread(self.get_payment, payment_id)
