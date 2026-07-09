import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import get_settings
from bot.services.supabase_service import SupabaseService


def main() -> None:
    settings = get_settings()
    supabase = SupabaseService(settings)
    client = supabase.client
    payment_id = f"codex-test-{uuid4()}"
    telegram_id = 900000000001

    try:
        supabase.check_connection()
        print("select: ok")

        created = supabase.create_pending_payment(telegram_id, payment_id)
        assert created["payment_id"] == payment_id
        assert created["telegram_id"] == telegram_id
        assert created["status"] == "pending"
        print("insert pending: ok")

        found = supabase.get_payment_by_payment_id(payment_id)
        assert found and found["payment_id"] == payment_id
        print("lookup by payment_id: ok")

        updated = supabase.mark_payment_succeeded(payment_id)
        assert updated and updated["status"] == "succeeded"
        print("update status: ok")

        paid = supabase.get_succeeded_payment_by_user(telegram_id)
        assert paid and paid["payment_id"] == payment_id
        print("lookup succeeded by user: ok")

        invite = supabase.set_invite_sent(payment_id)
        assert invite and invite["invite_sent"] is True
        print("update invite_sent: ok")
    finally:
        client.table("payments").delete().eq("payment_id", payment_id).execute()
        print("cleanup: ok")


if __name__ == "__main__":
    main()
