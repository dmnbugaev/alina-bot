import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bot.services.payment_orchestrator import (
    PaymentOrchestrator,
    PaymentValidationError,
)
from bot.services.yookassa_service import PaymentSnapshot
from tests.conftest import make_settings


class FakeSupabase:
    def __init__(self):
        self.payment = None
        self.delivery = None
        self.events = []
        self._lock = asyncio.Lock()

    async def get_active_payment_async(self, telegram_id):
        if self.payment and self.payment["status"] in {"creating", "pending"}:
            return dict(self.payment)
        return None

    async def create_payment_intent_async(
        self,
        telegram_id,
        idempotency_key,
        amount,
        currency,
        source,
    ):
        async with self._lock:
            if self.payment and self.payment["status"] in {"creating", "pending"}:
                raise RuntimeError("duplicate open payment")
            self.payment = {
                "id": 1,
                "telegram_id": telegram_id,
                "payment_id": None,
                "idempotency_key": idempotency_key,
                "amount": str(amount),
                "currency": currency,
                "source": source,
                "status": "creating",
                "check_attempts": 0,
            }
            return dict(self.payment)

    async def finalize_payment_intent_async(
        self,
        local_id,
        payment_id,
        confirmation_url,
        provider_expires_at,
    ):
        self.payment.update(
            {
                "payment_id": payment_id,
                "confirmation_url": confirmation_url,
                "provider_expires_at": provider_expires_at,
                "status": "pending",
            }
        )
        return dict(self.payment)

    async def record_event_async(
        self,
        telegram_id,
        event_type,
        source="organic",
        payment_id=None,
        properties=None,
    ):
        self.events.append((telegram_id, event_type, source, payment_id, properties))

    async def update_payment_status_async(
        self,
        local_id,
        status,
        check_attempts,
        next_check_at=None,
        error=None,
    ):
        self.payment.update(
            {
                "status": status,
                "check_attempts": check_attempts,
                "next_check_at": next_check_at,
                "last_error": error,
            }
        )
        return dict(self.payment)

    async def claim_access_delivery_async(self, payment_id, telegram_id):
        if self.delivery and self.delivery["status"] == "delivered":
            return None
        if self.delivery is None:
            self.delivery = {
                "payment_id": payment_id,
                "telegram_id": telegram_id,
                "status": "processing",
                "attempt_count": 1,
                "invite_link": None,
                "invite_expires_at": None,
            }
        return dict(self.delivery)

    async def get_access_delivery_by_user_async(self, telegram_id):
        return dict(self.delivery) if self.delivery else None

    async def save_invite_link_async(self, payment_id, invite_link, expires_at):
        self.delivery.update(
            {
                "invite_link": invite_link,
                "invite_expires_at": expires_at,
                "status": "processing",
            }
        )
        return dict(self.delivery)

    async def mark_access_delivered_async(self, payment_id):
        self.delivery["status"] = "delivered"

    async def mark_access_failed_async(self, payment_id, error, delay):
        self.delivery.update({"status": "failed", "last_error": error})
        return dict(self.delivery)


class FakeYooKassa:
    def __init__(self, telegram_id=42):
        self.telegram_id = telegram_id
        self.created_count = 0
        self._payments = {}
        self.status = "pending"
        self.paid = False
        self._lock = asyncio.Lock()

    def snapshot(self, payment_id):
        return PaymentSnapshot(
            payment_id=payment_id,
            status=self.status,
            paid=self.paid,
            amount=Decimal("499.00"),
            currency="RUB",
            metadata={"telegram_id": str(self.telegram_id)},
            confirmation_url="https://yookassa.test/pay",
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )

    async def create_payment_async(self, telegram_id, idempotency_key):
        async with self._lock:
            if idempotency_key not in self._payments:
                self.created_count += 1
                self._payments[idempotency_key] = f"pay-{self.created_count}"
            return self.snapshot(self._payments[idempotency_key])

    async def get_payment_async(self, payment_id):
        return self.snapshot(payment_id)


class FakeTelegram:
    def __init__(self):
        self.created_links = 0
        self.sent_links = 0
        self.alerts = []

    async def create_one_time_invite_link(self, payment_id):
        self.created_links += 1
        return "https://t.me/+invite", datetime(2030, 1, 1, tzinfo=UTC)

    async def send_invite_link(self, telegram_id, invite_link):
        self.sent_links += 1

    async def notify_admins(self, text):
        self.alerts.append(text)


@pytest.mark.asyncio
async def test_repeated_callbacks_create_one_provider_payment():
    supabase = FakeSupabase()
    yookassa = FakeYooKassa()
    orchestrator = PaymentOrchestrator(make_settings(), supabase, yookassa)

    first, second = await asyncio.gather(
        orchestrator.get_or_create_checkout(42, "organic"),
        orchestrator.get_or_create_checkout(42, "organic"),
    )

    assert first["payment_id"] == second["payment_id"]
    assert yookassa.created_count == 1


@pytest.mark.asyncio
async def test_succeeded_payment_creates_and_sends_one_invite():
    supabase = FakeSupabase()
    yookassa = FakeYooKassa()
    telegram = FakeTelegram()
    orchestrator = PaymentOrchestrator(make_settings(), supabase, yookassa)
    payment = await orchestrator.get_or_create_checkout(42, "organic")
    yookassa.status = "succeeded"
    yookassa.paid = True

    first = await orchestrator.sync_payment(payment, telegram)
    second = await orchestrator.sync_payment(supabase.payment, telegram)

    assert first.status == "delivered"
    assert second.status == "delivered"
    assert telegram.created_links == 1
    assert telegram.sent_links == 1
    assert supabase.delivery["status"] == "delivered"


def test_snapshot_validation_rejects_wrong_user():
    settings = make_settings()
    orchestrator = PaymentOrchestrator(settings, FakeSupabase(), FakeYooKassa())
    snapshot = PaymentSnapshot(
        payment_id="pay-1",
        status="succeeded",
        paid=True,
        amount=Decimal("499.00"),
        currency="RUB",
        metadata={"telegram_id": "999"},
    )

    with pytest.raises(PaymentValidationError):
        orchestrator.validate_snapshot(
            snapshot,
            42,
            {
                "payment_id": "pay-1",
                "amount": "499.00",
                "currency": "RUB",
            },
        )
