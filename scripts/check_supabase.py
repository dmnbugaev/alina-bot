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
    created = False

    print(f"test payment_id: {payment_id}", flush=True)

    try:
        supabase.check_connection()
        print("select: ok", flush=True)

        created_payment = supabase.create_pending_payment(telegram_id, payment_id)
        created = True
        assert created_payment["payment_id"] == payment_id
        assert created_payment["telegram_id"] == telegram_id
        assert created_payment["status"] == "pending"
        print("insert pending: ok", flush=True)

        found = supabase.get_payment_by_payment_id(payment_id)
        assert found and found["payment_id"] == payment_id
        print("lookup by payment_id: ok", flush=True)

        updated = supabase.mark_payment_succeeded(payment_id)
        assert updated and updated["status"] == "succeeded"
        print("update status: ok", flush=True)

        paid = supabase.get_succeeded_payment_by_user(telegram_id)
        assert paid and paid["payment_id"] == payment_id
        print("lookup succeeded by user: ok", flush=True)

        invite = supabase.set_invite_sent(payment_id)
        assert invite and invite["invite_sent"] is True
        print("update invite_sent: ok", flush=True)
    finally:
        if created:
            try:
                client.table("payments").delete().eq("payment_id", payment_id).execute()
                print("cleanup: ok", flush=True)
            except Exception as exc:
                print(f"cleanup failed for {payment_id}: {exc}", file=sys.stderr, flush=True)
                raise


if __name__ == "__main__":
    main()
