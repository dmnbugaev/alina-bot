import logging
from asyncio import to_thread
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from bot.config import Settings
from supabase import Client, create_client

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SupabaseService:
    def __init__(self, settings: Settings):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        self.table_name = "payments"

    def check_connection(self) -> bool:
        self.client.table(self.table_name).select("id").limit(1).execute()
        return True

    async def check_connection_async(self) -> bool:
        return await to_thread(self.check_connection)

    def record_user(self, telegram_id: int, source: str) -> None:
        existing = (
            self.client.table("bot_users")
            .select("telegram_id")
            .eq("telegram_id", telegram_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            (
                self.client.table("bot_users")
                .update({"last_seen_at": utc_now_iso()})
                .eq("telegram_id", telegram_id)
                .execute()
            )
        else:
            try:
                self.client.table("bot_users").insert(
                    {
                        "telegram_id": telegram_id,
                        "source": source,
                        "last_seen_at": utc_now_iso(),
                    }
                ).execute()
            except Exception:
                # A concurrent /start may have inserted the same Telegram user.
                (
                    self.client.table("bot_users")
                    .update({"last_seen_at": utc_now_iso()})
                    .eq("telegram_id", telegram_id)
                    .execute()
                )

    async def record_user_async(self, telegram_id: int, source: str) -> None:
        await to_thread(self.record_user, telegram_id, source)

    def get_user_source(self, telegram_id: int) -> str:
        response = (
            self.client.table("bot_users")
            .select("source")
            .eq("telegram_id", telegram_id)
            .limit(1)
            .execute()
        )
        return str(response.data[0]["source"]) if response.data else "organic"

    async def get_user_source_async(self, telegram_id: int) -> str:
        return await to_thread(self.get_user_source, telegram_id)

    def record_event(
        self,
        telegram_id: int,
        event_type: str,
        source: str = "organic",
        payment_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self.client.table("funnel_events").insert(
            {
                "telegram_id": telegram_id,
                "event_type": event_type,
                "source": source,
                "payment_id": payment_id,
                "properties": properties or {},
            }
        ).execute()

    async def record_event_async(self, *args: Any, **kwargs: Any) -> None:
        await to_thread(self.record_event, *args, **kwargs)

    def get_active_payment(self, telegram_id: int) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("telegram_id", telegram_id)
            .in_("status", ["creating", "pending"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_active_payment_async(self, telegram_id: int) -> dict[str, Any] | None:
        return await to_thread(self.get_active_payment, telegram_id)

    def create_payment_intent(
        self,
        telegram_id: int,
        idempotency_key: str,
        amount: Decimal,
        currency: str,
        source: str,
    ) -> dict[str, Any]:
        response = (
            self.client.table(self.table_name)
            .insert(
                {
                    "telegram_id": telegram_id,
                    "payment_id": None,
                    "idempotency_key": idempotency_key,
                    "status": "creating",
                    "amount": f"{amount:.2f}",
                    "currency": currency,
                    "source": source,
                    "next_check_at": utc_now_iso(),
                }
            )
            .execute()
        )
        if not response.data:
            raise RuntimeError("Supabase did not return the created payment intent")
        return response.data[0]

    async def create_payment_intent_async(
        self,
        telegram_id: int,
        idempotency_key: str,
        amount: Decimal,
        currency: str,
        source: str,
    ) -> dict[str, Any]:
        return await to_thread(
            self.create_payment_intent,
            telegram_id,
            idempotency_key,
            amount,
            currency,
            source,
        )

    def finalize_payment_intent(
        self,
        local_id: int,
        payment_id: str,
        confirmation_url: str | None,
        provider_expires_at: str | datetime | None,
    ) -> dict[str, Any]:
        expires_at = (
            provider_expires_at.isoformat()
            if isinstance(provider_expires_at, datetime)
            else provider_expires_at
        )
        response = (
            self.client.table(self.table_name)
            .update(
                {
                    "payment_id": payment_id,
                    "confirmation_url": confirmation_url,
                    "provider_expires_at": expires_at,
                    "status": "pending",
                    "next_check_at": (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
                    "last_error": None,
                }
            )
            .eq("id", local_id)
            .execute()
        )
        if not response.data:
            raise RuntimeError(f"Payment intent {local_id} was not finalized")
        return response.data[0]

    async def finalize_payment_intent_async(
        self,
        local_id: int,
        payment_id: str,
        confirmation_url: str | None,
        provider_expires_at: str | datetime | None,
    ) -> dict[str, Any]:
        return await to_thread(
            self.finalize_payment_intent,
            local_id,
            payment_id,
            confirmation_url,
            provider_expires_at,
        )

    def update_payment_status(
        self,
        local_id: int,
        status: str,
        check_attempts: int,
        next_check_at: datetime | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "status": status,
            "last_error": error,
            "check_attempts": check_attempts,
        }
        if next_check_at:
            payload["next_check_at"] = next_check_at.isoformat()
        if status == "succeeded":
            payload["succeeded_at"] = utc_now_iso()
        elif status == "canceled":
            payload["canceled_at"] = utc_now_iso()
        response = self.client.table(self.table_name).update(payload).eq("id", local_id).execute()
        return response.data[0] if response.data else None

    async def update_payment_status_async(
        self,
        local_id: int,
        status: str,
        check_attempts: int,
        next_check_at: datetime | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        return await to_thread(
            self.update_payment_status,
            local_id,
            status,
            check_attempts,
            next_check_at,
            error,
        )

    def list_due_payments(self, limit: int) -> list[dict[str, Any]]:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .in_("status", ["creating", "pending"])
            .lte("next_check_at", utc_now_iso())
            .order("next_check_at")
            .limit(limit)
            .execute()
        )
        return list(response.data or [])

    async def list_due_payments_async(self, limit: int) -> list[dict[str, Any]]:
        return await to_thread(self.list_due_payments, limit)

    def get_latest_payment_by_user(self, telegram_id: int) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("telegram_id", telegram_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_latest_payment_by_user_async(
        self,
        telegram_id: int,
    ) -> dict[str, Any] | None:
        return await to_thread(self.get_latest_payment_by_user, telegram_id)

    def get_payment_by_payment_id(self, payment_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("payment_id", payment_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_payment_by_payment_id_async(
        self,
        payment_id: str,
    ) -> dict[str, Any] | None:
        return await to_thread(self.get_payment_by_payment_id, payment_id)

    def claim_access_delivery(
        self,
        payment_id: str,
        telegram_id: int,
    ) -> dict[str, Any] | None:
        response = self.client.rpc(
            "claim_access_delivery",
            {"p_payment_id": payment_id, "p_telegram_id": telegram_id},
        ).execute()
        return response.data[0] if response.data else None

    async def claim_access_delivery_async(
        self,
        payment_id: str,
        telegram_id: int,
    ) -> dict[str, Any] | None:
        return await to_thread(
            self.claim_access_delivery,
            payment_id,
            telegram_id,
        )

    def get_access_delivery_by_user(
        self,
        telegram_id: int,
    ) -> dict[str, Any] | None:
        response = (
            self.client.table("access_deliveries")
            .select("*")
            .eq("telegram_id", telegram_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_access_delivery_by_user_async(
        self,
        telegram_id: int,
    ) -> dict[str, Any] | None:
        return await to_thread(self.get_access_delivery_by_user, telegram_id)

    def save_invite_link(
        self,
        payment_id: str,
        invite_link: str,
        expires_at: datetime,
    ) -> dict[str, Any] | None:
        response = (
            self.client.table("access_deliveries")
            .update(
                {
                    "status": "processing",
                    "invite_link": invite_link,
                    "invite_expires_at": expires_at.isoformat(),
                    "next_retry_at": utc_now_iso(),
                    "last_error": None,
                }
            )
            .eq("payment_id", payment_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def save_invite_link_async(
        self,
        payment_id: str,
        invite_link: str,
        expires_at: datetime,
    ) -> dict[str, Any] | None:
        return await to_thread(
            self.save_invite_link,
            payment_id,
            invite_link,
            expires_at,
        )

    def mark_access_delivered(self, payment_id: str) -> None:
        (
            self.client.table("access_deliveries")
            .update(
                {
                    "status": "delivered",
                    "sent_at": utc_now_iso(),
                    "last_error": None,
                }
            )
            .eq("payment_id", payment_id)
            .execute()
        )
        (
            self.client.table(self.table_name)
            .update({"invite_sent": True})
            .eq("payment_id", payment_id)
            .execute()
        )

    async def mark_access_delivered_async(self, payment_id: str) -> None:
        await to_thread(self.mark_access_delivered, payment_id)

    def mark_access_failed(
        self,
        payment_id: str,
        error: str,
        delay: timedelta,
    ) -> dict[str, Any] | None:
        response = (
            self.client.table("access_deliveries")
            .update(
                {
                    "status": "failed",
                    "last_error": error[:1000],
                    "next_retry_at": (datetime.now(UTC) + delay).isoformat(),
                }
            )
            .eq("payment_id", payment_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def mark_access_failed_async(
        self,
        payment_id: str,
        error: str,
        delay: timedelta,
    ) -> dict[str, Any] | None:
        return await to_thread(
            self.mark_access_failed,
            payment_id,
            error,
            delay,
        )

    def mark_delivery_alerted(self, payment_id: str) -> None:
        (
            self.client.table("access_deliveries")
            .update({"last_alerted_at": utc_now_iso()})
            .eq("payment_id", payment_id)
            .execute()
        )

    async def mark_delivery_alerted_async(self, payment_id: str) -> None:
        await to_thread(self.mark_delivery_alerted, payment_id)

    def list_due_deliveries(self, limit: int) -> list[dict[str, Any]]:
        response = (
            self.client.table("access_deliveries")
            .select("*")
            .in_("status", ["pending", "failed", "link_ready", "processing"])
            .lte("next_retry_at", utc_now_iso())
            .order("next_retry_at")
            .limit(limit)
            .execute()
        )
        return list(response.data or [])

    async def list_due_deliveries_async(
        self,
        limit: int,
    ) -> list[dict[str, Any]]:
        return await to_thread(self.list_due_deliveries, limit)

    def list_pending_for_reminders(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("status", "pending")
            .not_.is_("confirmation_url", "null")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return list(response.data or [])

    async def list_pending_for_reminders_async(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await to_thread(self.list_pending_for_reminders, limit)

    def mark_reminder_sent(self, local_id: int, number: int) -> None:
        column = "reminder_1_sent_at" if number == 1 else "reminder_2_sent_at"
        (
            self.client.table(self.table_name)
            .update({column: utc_now_iso()})
            .eq("id", local_id)
            .execute()
        )

    async def mark_reminder_sent_async(
        self,
        local_id: int,
        number: int,
    ) -> None:
        await to_thread(self.mark_reminder_sent, local_id, number)

    def get_events_since(self, since: datetime) -> list[dict[str, Any]]:
        response = (
            self.client.table("funnel_events")
            .select("*")
            .gte("created_at", since.isoformat())
            .execute()
        )
        return list(response.data or [])

    async def get_events_since_async(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        return await to_thread(self.get_events_since, since)

    def get_payments_since(self, since: datetime) -> list[dict[str, Any]]:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .gte("created_at", since.isoformat())
            .execute()
        )
        return list(response.data or [])

    async def get_payments_since_async(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        return await to_thread(self.get_payments_since, since)

    def get_unresolved_delivery_errors(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        response = (
            self.client.table("access_deliveries")
            .select("*")
            .eq("status", "failed")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(response.data or [])

    async def get_unresolved_delivery_errors_async(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return await to_thread(self.get_unresolved_delivery_errors, limit)

    # Compatibility helpers for scripts/check_supabase.py.
    def create_pending_payment(
        self,
        telegram_id: int,
        payment_id: str,
    ) -> dict[str, Any]:
        response = (
            self.client.table(self.table_name)
            .insert(
                {
                    "telegram_id": telegram_id,
                    "payment_id": payment_id,
                    "idempotency_key": f"diagnostic-{payment_id}",
                    "status": "pending",
                }
            )
            .execute()
        )
        return response.data[0]

    def mark_payment_succeeded(
        self,
        payment_id: str,
    ) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .update(
                {
                    "status": "succeeded",
                    "succeeded_at": utc_now_iso(),
                }
            )
            .eq("payment_id", payment_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def get_succeeded_payment_by_user(
        self,
        telegram_id: int,
    ) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("telegram_id", telegram_id)
            .eq("status", "succeeded")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def set_invite_sent(
        self,
        payment_id: str,
    ) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .update({"invite_sent": True})
            .eq("payment_id", payment_id)
            .execute()
        )
        return response.data[0] if response.data else None
