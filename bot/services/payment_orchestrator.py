import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from bot.config import Settings
from bot.services.supabase_service import SupabaseService
from bot.services.telegram_service import TelegramService
from bot.services.yookassa_service import PaymentSnapshot, YooKassaService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SyncResult:
    status: str
    payment: dict[str, Any]
    delivery: dict[str, Any] | None = None


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class PaymentValidationError(RuntimeError):
    pass


class PaymentOrchestrator:
    def __init__(
        self,
        settings: Settings,
        supabase: SupabaseService,
        yookassa: YooKassaService,
    ):
        self.settings = settings
        self.supabase = supabase
        self.yookassa = yookassa

    async def _safe_event(
        self,
        telegram_id: int,
        event_type: str,
        source: str = "organic",
        payment_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        try:
            await self.supabase.record_event_async(
                telegram_id,
                event_type,
                source,
                payment_id,
                properties,
            )
        except Exception:
            logger.exception("Failed to record funnel event %s", event_type)

    def validate_snapshot(
        self,
        snapshot: PaymentSnapshot,
        telegram_id: int,
        payment: dict[str, Any],
    ) -> None:
        metadata_telegram_id = str(snapshot.metadata.get("telegram_id", ""))
        if snapshot.payment_id != payment.get("payment_id"):
            raise PaymentValidationError("YooKassa payment ID does not match local payment")
        if metadata_telegram_id != str(telegram_id):
            raise PaymentValidationError("YooKassa metadata.telegram_id does not match")
        expected_amount = payment.get("amount")
        if expected_amount is not None and snapshot.amount != Decimal(str(expected_amount)):
            raise PaymentValidationError("YooKassa amount does not match local payment")
        expected_currency = payment.get("currency")
        if expected_currency is not None and snapshot.currency != str(expected_currency).upper():
            raise PaymentValidationError("YooKassa currency does not match local payment")

    async def get_or_create_checkout(
        self,
        telegram_id: int,
        source: str,
    ) -> dict[str, Any]:
        payment = await self.supabase.get_active_payment_async(telegram_id)
        if payment and payment.get("status") == "pending" and payment.get("confirmation_url"):
            expires_at = parse_datetime(payment.get("provider_expires_at"))
            if expires_at is None or expires_at > datetime.now(UTC):
                return payment
            await self.supabase.update_payment_status_async(
                int(payment["id"]),
                "canceled",
                int(payment.get("check_attempts") or 0),
                error="Provider payment expired before checkout reuse",
            )
            payment = None

        if payment is None:
            idempotency_key = str(uuid4())
            try:
                payment = await self.supabase.create_payment_intent_async(
                    telegram_id,
                    idempotency_key,
                    self.settings.payment_amount,
                    self.settings.payment_currency,
                    source,
                )
            except Exception:
                # A concurrent callback may have won the partial unique index.
                payment = await self.supabase.get_active_payment_async(telegram_id)
                if payment is None:
                    raise

        return await self._create_provider_payment(payment)

    async def _create_provider_payment(
        self,
        payment: dict[str, Any],
    ) -> dict[str, Any]:
        telegram_id = int(payment["telegram_id"])
        snapshot = await self.yookassa.create_payment_async(
            telegram_id,
            str(payment["idempotency_key"]),
        )
        provisional = {**payment, "payment_id": snapshot.payment_id}
        self.validate_snapshot(snapshot, telegram_id, provisional)
        finalized = await self.supabase.finalize_payment_intent_async(
            int(payment["id"]),
            snapshot.payment_id,
            snapshot.confirmation_url,
            snapshot.expires_at,
        )
        await self._safe_event(
            telegram_id,
            "payment_created",
            str(payment.get("source") or "organic"),
            snapshot.payment_id,
        )
        return finalized

    @staticmethod
    def _next_check_delay(attempt: int) -> timedelta:
        seconds = (30, 60, 120, 300, 900, 1800)
        return timedelta(seconds=seconds[min(max(attempt - 1, 0), len(seconds) - 1)])

    @staticmethod
    def _delivery_retry_delay(attempt: int) -> timedelta:
        minutes = (1, 5, 15, 60, 360)
        return timedelta(minutes=minutes[min(max(attempt - 1, 0), len(minutes) - 1)])

    async def sync_payment(
        self,
        payment: dict[str, Any],
        telegram: TelegramService,
    ) -> SyncResult:
        if payment.get("status") == "succeeded":
            delivery = await self.fulfill_payment(payment, telegram)
            status = (
                "delivered" if delivery and delivery.get("status") == "delivered" else "succeeded"
            )
            return SyncResult(status, payment, delivery)

        if payment.get("status") == "creating" or not payment.get("payment_id"):
            payment = await self._create_provider_payment(payment)

        attempt = int(payment.get("check_attempts") or 0) + 1
        try:
            snapshot = await self.yookassa.get_payment_async(str(payment["payment_id"]))
            self.validate_snapshot(snapshot, int(payment["telegram_id"]), payment)
        except Exception as exc:
            await self.supabase.update_payment_status_async(
                int(payment["id"]),
                "pending",
                attempt,
                datetime.now(UTC) + self._next_check_delay(attempt),
                str(exc),
            )
            raise

        if snapshot.status == "succeeded" and snapshot.paid:
            was_succeeded = payment.get("status") == "succeeded"
            payment = (
                await self.supabase.update_payment_status_async(
                    int(payment["id"]),
                    "succeeded",
                    attempt,
                )
                or payment
            )
            if not was_succeeded:
                await self._safe_event(
                    int(payment["telegram_id"]),
                    "payment_succeeded",
                    str(payment.get("source") or "organic"),
                    str(payment["payment_id"]),
                )
            delivery = await self.fulfill_payment(payment, telegram)
            status = (
                "delivered" if delivery and delivery.get("status") == "delivered" else "succeeded"
            )
            return SyncResult(status, payment, delivery)

        if snapshot.status == "canceled":
            payment = (
                await self.supabase.update_payment_status_async(
                    int(payment["id"]),
                    "canceled",
                    attempt,
                )
                or payment
            )
            return SyncResult("canceled", payment)

        expires_at = parse_datetime(payment.get("provider_expires_at"))
        if expires_at and expires_at <= datetime.now(UTC):
            payment = (
                await self.supabase.update_payment_status_async(
                    int(payment["id"]),
                    "canceled",
                    attempt,
                    error="Provider payment expired",
                )
                or payment
            )
            return SyncResult("canceled", payment)

        payment = (
            await self.supabase.update_payment_status_async(
                int(payment["id"]),
                "pending",
                attempt,
                datetime.now(UTC) + self._next_check_delay(attempt),
            )
            or payment
        )
        return SyncResult("pending", payment)

    async def fulfill_payment(
        self,
        payment: dict[str, Any],
        telegram: TelegramService,
    ) -> dict[str, Any] | None:
        payment_id = str(payment["payment_id"])
        telegram_id = int(payment["telegram_id"])
        delivery = await self.supabase.claim_access_delivery_async(
            payment_id,
            telegram_id,
        )
        if delivery is None:
            return await self.supabase.get_access_delivery_by_user_async(telegram_id)

        try:
            invite_link = delivery.get("invite_link")
            invite_expires_at = parse_datetime(delivery.get("invite_expires_at"))
            if not invite_link or not invite_expires_at or invite_expires_at <= datetime.now(UTC):
                invite_link, invite_expires_at = await telegram.create_one_time_invite_link(
                    payment_id,
                )
                delivery = (
                    await self.supabase.save_invite_link_async(
                        payment_id,
                        invite_link,
                        invite_expires_at,
                    )
                    or delivery
                )

            await telegram.send_invite_link(telegram_id, invite_link)
            await self.supabase.mark_access_delivered_async(payment_id)
            await self._safe_event(
                telegram_id,
                "access_sent",
                str(payment.get("source") or "organic"),
                payment_id,
            )
            return {**delivery, "status": "delivered"}
        except Exception as exc:
            attempt = int(delivery.get("attempt_count") or 1)
            failed = await self.supabase.mark_access_failed_async(
                payment_id,
                str(exc),
                self._delivery_retry_delay(attempt),
            )
            logger.exception("Access delivery failed for payment_id=%s", payment_id)
            last_alerted_at = parse_datetime(delivery.get("last_alerted_at"))
            alert_due = last_alerted_at is None or last_alerted_at <= datetime.now(UTC) - timedelta(
                hours=6
            )
            if attempt >= 3 and alert_due:
                await telegram.notify_admins(
                    "⚠️ Не удалось выдать оплаченный доступ\n"
                    f"payment_id: {payment_id}\n"
                    f"telegram_id: {telegram_id}\n"
                    f"попытка: {attempt}\n"
                    f"ошибка: {type(exc).__name__}",
                )
                await self.supabase.mark_delivery_alerted_async(payment_id)
            return failed
