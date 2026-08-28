import asyncio
import logging
from datetime import UTC, datetime

from bot.config import Settings
from bot.services.payment_orchestrator import PaymentOrchestrator, parse_datetime
from bot.services.supabase_service import SupabaseService
from bot.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class PaymentWorker:
    def __init__(
        self,
        settings: Settings,
        supabase: SupabaseService,
        orchestrator: PaymentOrchestrator,
    ):
        self.settings = settings
        self.supabase = supabase
        self.orchestrator = orchestrator
        self.last_cycle_at: datetime | None = None
        self.last_error: str | None = None

    async def run(self, telegram: TelegramService) -> None:
        logger.info("Payment worker started")
        while True:
            try:
                await self.run_cycle(telegram)
                self.last_cycle_at = datetime.now(UTC)
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.exception("Payment worker cycle failed")
            await asyncio.sleep(self.settings.payment_poll_interval_seconds)

    async def run_cycle(self, telegram: TelegramService) -> None:
        if self.settings.auto_fulfillment_enabled:
            await self._sync_due_payments(telegram)
            await self._retry_due_deliveries(telegram)
        if self.settings.reminders_enabled:
            await self._send_due_reminders(telegram)

    async def _sync_due_payments(self, telegram: TelegramService) -> None:
        payments = await self.supabase.list_due_payments_async(
            self.settings.payment_poll_batch_size,
        )
        for payment in payments:
            try:
                await self.orchestrator.sync_payment(payment, telegram)
            except Exception:
                logger.exception(
                    "Failed to synchronize local payment id=%s",
                    payment.get("id"),
                )

    async def _retry_due_deliveries(self, telegram: TelegramService) -> None:
        deliveries = await self.supabase.list_due_deliveries_async(
            self.settings.payment_poll_batch_size,
        )
        for delivery in deliveries:
            payment = await self.supabase.get_payment_by_payment_id_async(
                str(delivery["payment_id"]),
            )
            if not payment or payment.get("status") != "succeeded":
                continue
            await self.orchestrator.fulfill_payment(payment, telegram)

    async def _send_due_reminders(self, telegram: TelegramService) -> None:
        now = datetime.now(UTC)
        first_hour, second_hour = self.settings.reminder_hours
        payments = await self.supabase.list_pending_for_reminders_async()
        for payment in payments:
            created_at = parse_datetime(payment.get("created_at"))
            if created_at is None:
                continue
            age_hours = (now - created_at).total_seconds() / 3600
            number: int | None = None
            if age_hours >= second_hour and not payment.get("reminder_2_sent_at"):
                number = 2
            elif age_hours >= first_hour and not payment.get("reminder_1_sent_at"):
                number = 1
            if number is None:
                continue

            try:
                result = await self.orchestrator.sync_payment(payment, telegram)
                if result.status != "pending":
                    continue
                await telegram.send_payment_reminder(
                    int(payment["telegram_id"]),
                    str(payment["confirmation_url"]),
                    final=number == 2,
                )
                await self.supabase.mark_reminder_sent_async(int(payment["id"]), number)
                if number == 2 and not payment.get("reminder_1_sent_at"):
                    await self.supabase.mark_reminder_sent_async(int(payment["id"]), 1)
                await self.supabase.record_event_async(
                    int(payment["telegram_id"]),
                    "reminder_sent",
                    str(payment.get("source") or "organic"),
                    str(payment["payment_id"]),
                    {"number": number},
                )
            except Exception:
                logger.exception(
                    "Failed to send reminder for local payment id=%s",
                    payment.get("id"),
                )
