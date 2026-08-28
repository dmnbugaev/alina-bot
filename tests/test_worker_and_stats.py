from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from bot.handlers.admin import metrics_for_period
from bot.services.worker import PaymentWorker
from tests.conftest import make_settings


class ReminderSupabase:
    def __init__(self):
        self.payment = {
            "id": 1,
            "telegram_id": 42,
            "payment_id": "pay-1",
            "status": "pending",
            "source": "organic",
            "confirmation_url": "https://yookassa.test/pay",
            "created_at": (datetime.now(UTC) - timedelta(hours=25)).isoformat(),
            "reminder_1_sent_at": None,
            "reminder_2_sent_at": None,
        }
        self.sent_numbers = []
        self.events = []

    async def list_pending_for_reminders_async(self):
        return [dict(self.payment)]

    async def mark_reminder_sent_async(self, local_id, number):
        self.sent_numbers.append(number)

    async def record_event_async(self, *args, **kwargs):
        self.events.append((args, kwargs))


class PendingOrchestrator:
    async def sync_payment(self, payment, telegram):
        return SimpleNamespace(status="pending")


class ReminderTelegram:
    def __init__(self):
        self.messages = []

    async def send_payment_reminder(self, telegram_id, payment_url, final):
        self.messages.append((telegram_id, payment_url, final))


@pytest.mark.asyncio
async def test_worker_sends_only_final_reminder_after_24_hours():
    supabase = ReminderSupabase()
    worker = PaymentWorker(
        make_settings(REMINDERS_ENABLED=True),
        supabase,
        PendingOrchestrator(),
    )
    telegram = ReminderTelegram()

    await worker._send_due_reminders(telegram)

    assert telegram.messages == [(42, "https://yookassa.test/pay", True)]
    assert supabase.sent_numbers == [2, 1]
    assert len(supabase.events) == 1


def test_metrics_report_conversion_and_revenue():
    now = datetime.now(UTC)
    events = [
        {"telegram_id": 1, "event_type": "start", "created_at": now.isoformat()},
        {"telegram_id": 2, "event_type": "start", "created_at": now.isoformat()},
        {
            "telegram_id": 1,
            "event_type": "payment_succeeded",
            "created_at": now.isoformat(),
        },
        {"telegram_id": 1, "event_type": "access_sent", "created_at": now.isoformat()},
    ]
    payments = [
        {
            "telegram_id": 1,
            "status": "succeeded",
            "amount": "499.00",
            "created_at": now.isoformat(),
        }
    ]

    result = metrics_for_period(events, payments, now - timedelta(days=1))

    assert "конверсия start → оплата: 50.0%" in result
    assert "выручка: 499.00 ₽" in result
