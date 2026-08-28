from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import get_settings
from bot.services.factory import get_payment_worker, get_supabase_service
from bot.services.payment_orchestrator import parse_datetime

router = Router()


def is_admin(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in get_settings().admin_ids)


def metrics_for_period(
    events: list[dict],
    payments: list[dict],
    since: datetime,
) -> str:
    period_events = [
        event
        for event in events
        if (parse_datetime(event.get("created_at")) or datetime.min.replace(tzinfo=UTC)) >= since
    ]
    period_payments = [
        payment
        for payment in payments
        if (parse_datetime(payment.get("created_at")) or datetime.min.replace(tzinfo=UTC)) >= since
    ]
    counts = Counter(event["event_type"] for event in period_events)
    starts = {
        int(event["telegram_id"]) for event in period_events if event["event_type"] == "start"
    }
    paid_users = {
        int(event["telegram_id"])
        for event in period_events
        if event["event_type"] == "payment_succeeded"
    }
    revenue = sum(
        (
            Decimal(str(payment.get("amount") or "0"))
            for payment in period_payments
            if payment.get("status") == "succeeded"
        ),
        Decimal("0"),
    )
    conversion = (len(paid_users) / len(starts) * 100) if starts else 0
    pending = sum(
        1 for payment in period_payments if payment.get("status") in {"creating", "pending"}
    )
    return (
        f"старты: {len(starts)}\n"
        f"нажатия оплаты: {counts['buy_clicked']}\n"
        f"создано платежей: {counts['payment_created']}\n"
        f"успешно: {len(paid_users)}\n"
        f"доступов отправлено: {counts['access_sent']}\n"
        f"конверсия start → оплата: {conversion:.1f}%\n"
        f"выручка: {revenue:.2f} ₽\n"
        f"ожидают оплаты: {pending}"
    )


@router.message(Command("stats"))
async def stats_command(message: Message) -> None:
    if not is_admin(message):
        return
    supabase = get_supabase_service()
    now = datetime.now(UTC)
    events = await supabase.get_events_since_async(now - timedelta(days=30))
    payments = await supabase.get_payments_since_async(now - timedelta(days=30))
    text = (
        "Статистика\n\n"
        "24 часа\n"
        f"{metrics_for_period(events, payments, now - timedelta(days=1))}\n\n"
        "7 дней\n"
        f"{metrics_for_period(events, payments, now - timedelta(days=7))}\n\n"
        "30 дней\n"
        f"{metrics_for_period(events, payments, now - timedelta(days=30))}"
    )
    await message.answer(text)


@router.message(Command("errors"))
async def errors_command(message: Message) -> None:
    if not is_admin(message):
        return
    errors = await get_supabase_service().get_unresolved_delivery_errors_async()
    if not errors:
        await message.answer("Нерешённых ошибок выдачи нет.")
        return
    lines = ["Последние ошибки выдачи:"]
    for item in errors:
        lines.append(
            "\n"
            f"payment: {item.get('payment_id')}\n"
            f"user: {item.get('telegram_id')}\n"
            f"попыток: {item.get('attempt_count')}\n"
            f"ошибка: {item.get('last_error') or 'не указана'}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("health"))
async def health_command(message: Message) -> None:
    if not is_admin(message):
        return
    worker = get_payment_worker()
    try:
        await get_supabase_service().check_connection_async()
        database_status = "ok"
    except Exception as exc:
        database_status = f"error: {type(exc).__name__}"
    last_cycle = worker.last_cycle_at.isoformat() if worker.last_cycle_at else "ещё не запускался"
    await message.answer(
        "Состояние бота\n\n"
        f"Supabase: {database_status}\n"
        f"Worker: {last_cycle}\n"
        f"Последняя ошибка: {worker.last_error or 'нет'}\n"
        f"Автовыдача: {get_settings().auto_fulfillment_enabled}\n"
        f"Напоминания: {get_settings().reminders_enabled}",
    )
