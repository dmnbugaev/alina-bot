import logging
from asyncio import to_thread
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from yookassa import Configuration, Payment

from bot.config import Settings

logger = logging.getLogger(__name__)

# Явный срок жизни чекаута, чтобы payment_orchestrator мог переиспользовать
# ссылку только пока она реально оплачиваема.
CHECKOUT_TTL = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class PaymentSnapshot:
    payment_id: str
    status: str
    paid: bool
    amount: Decimal
    currency: str
    metadata: dict[str, Any]
    confirmation_url: str | None = None
    expires_at: datetime | str | None = None


class YooKassaService:
    def __init__(self, settings: Settings):
        self.settings = settings
        Configuration.account_id = settings.yookassa_shop_id
        Configuration.secret_key = settings.yookassa_secret_key

    @staticmethod
    def _to_snapshot(payment: Any) -> PaymentSnapshot:
        confirmation = getattr(payment, "confirmation", None)
        metadata = getattr(payment, "metadata", None) or {}
        return PaymentSnapshot(
            payment_id=str(payment.id),
            status=str(getattr(payment, "status", "unknown")),
            paid=bool(getattr(payment, "paid", False)),
            amount=Decimal(str(payment.amount.value)),
            currency=str(payment.amount.currency).upper(),
            metadata=dict(metadata),
            confirmation_url=getattr(confirmation, "confirmation_url", None),
            expires_at=getattr(payment, "expires_at", None),
        )

    def create_payment(self, telegram_id: int, idempotency_key: str) -> PaymentSnapshot:
        expires_at = (datetime.now(UTC) + CHECKOUT_TTL).replace(microsecond=0).isoformat()
        payment = Payment.create(
            {
                "amount": {
                    "value": f"{self.settings.payment_amount:.2f}",
                    "currency": self.settings.payment_currency,
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": self.settings.yookassa_return_url,
                },
                "capture": True,
                "expires_at": expires_at,
                "description": self.settings.payment_description,
                "metadata": {"telegram_id": str(telegram_id)},
            },
            idempotency_key,
        )
        logger.info("Created YooKassa payment %s for telegram_id=%s", payment.id, telegram_id)
        return self._to_snapshot(payment)

    async def create_payment_async(
        self,
        telegram_id: int,
        idempotency_key: str,
    ) -> PaymentSnapshot:
        return await to_thread(self.create_payment, telegram_id, idempotency_key)

    def get_payment(self, payment_id: str) -> PaymentSnapshot:
        return self._to_snapshot(Payment.find_one(payment_id))

    async def get_payment_async(self, payment_id: str) -> PaymentSnapshot:
        return await to_thread(self.get_payment, payment_id)
