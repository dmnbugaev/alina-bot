import logging
from asyncio import to_thread
from typing import Any

from supabase import Client, create_client

from bot.config import Settings

logger = logging.getLogger(__name__)


class SupabaseService:
    def __init__(self, settings: Settings):
        supabase_key = settings.supabase_service_role_key or settings.supabase_key
        self.client: Client = create_client(settings.supabase_url, supabase_key)
        self.table_name = "payments"

    def check_connection(self) -> bool:
        self.client.table(self.table_name).select("id").limit(1).execute()
        return True

    def get_succeeded_payment_by_user(self, telegram_id: int) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("telegram_id", telegram_id)
            .eq("status", "succeeded")
            .eq("invite_sent", False)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_succeeded_payment_by_user_async(self, telegram_id: int) -> dict[str, Any] | None:
        return await to_thread(self.get_succeeded_payment_by_user, telegram_id)

    def get_any_succeeded_payment_by_user(self, telegram_id: int) -> dict[str, Any] | None:
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

    async def get_any_succeeded_payment_by_user_async(self, telegram_id: int) -> dict[str, Any] | None:
        return await to_thread(self.get_any_succeeded_payment_by_user, telegram_id)

    def get_latest_pending_payment_by_user(self, telegram_id: int) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("telegram_id", telegram_id)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_latest_pending_payment_by_user_async(self, telegram_id: int) -> dict[str, Any] | None:
        return await to_thread(self.get_latest_pending_payment_by_user, telegram_id)

    def create_pending_payment(self, telegram_id: int, payment_id: str) -> dict[str, Any]:
        payload = {
            "telegram_id": telegram_id,
            "payment_id": payment_id,
            "status": "pending",
        }
        response = self.client.table(self.table_name).insert(payload).execute()
        logger.info("Saved pending payment %s for telegram_id=%s", payment_id, telegram_id)
        if not response.data:
            raise RuntimeError(f"Supabase did not return inserted payment {payment_id}")
        return response.data[0]

    async def create_pending_payment_async(self, telegram_id: int, payment_id: str) -> dict[str, Any]:
        return await to_thread(self.create_pending_payment, telegram_id, payment_id)

    def get_payment_by_payment_id(self, payment_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("payment_id", payment_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_payment_by_payment_id_async(self, payment_id: str) -> dict[str, Any] | None:
        return await to_thread(self.get_payment_by_payment_id, payment_id)

    def mark_payment_succeeded(self, payment_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .update({"status": "succeeded"})
            .eq("payment_id", payment_id)
            .execute()
        )
        logger.info("Marked payment %s as succeeded", payment_id)
        return response.data[0] if response.data else None

    async def mark_payment_succeeded_async(self, payment_id: str) -> dict[str, Any] | None:
        return await to_thread(self.mark_payment_succeeded, payment_id)

    def set_invite_sent(self, payment_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table_name)
            .update({"invite_sent": True})
            .eq("payment_id", payment_id)
            .execute()
        )
        logger.info("Marked invite as sent for payment %s", payment_id)
        return response.data[0] if response.data else None

    async def set_invite_sent_async(self, payment_id: str) -> dict[str, Any] | None:
        return await to_thread(self.set_invite_sent, payment_id)
