import logging

from aiogram import Router
from aiogram.types import CallbackQuery

from bot.config import get_settings
from bot.keyboards.inline import payment_keyboard
from bot.services.factory import get_supabase_service, get_yookassa_service
from bot.services.supabase_service import SupabaseService
from bot.services.telegram_service import InviteLinkError, TelegramService

logger = logging.getLogger(__name__)
router = Router()


async def send_invite_link(
    callback: CallbackQuery,
    telegram: TelegramService,
    supabase: SupabaseService,
    payment_id: str | None = None,
) -> None:
    invite_link = await telegram.create_one_time_invite_link()
    await callback.message.answer(
        "Оплата прошла успешно.\n\nВаша одноразовая ссылка:\n"
        f"{invite_link}"
    )
    if payment_id:
        await supabase.set_invite_sent_async(payment_id)


async def answer_if_invite_already_sent(callback: CallbackQuery, supabase: SupabaseService) -> bool:
    sent_payment = await supabase.get_any_succeeded_payment_by_user_async(callback.from_user.id)
    if sent_payment and sent_payment.get("invite_sent"):
        await callback.message.answer("Ссылка уже была отправлена. Если она не сработала, напишите: @a_vng")
        return True
    return False


@router.callback_query(lambda callback: callback.data == "get_access")
async def get_access(callback: CallbackQuery) -> None:
    await callback.answer()
    settings = get_settings()
    supabase = get_supabase_service()
    yookassa = get_yookassa_service()
    telegram = TelegramService(callback.bot, settings)

    telegram_id = callback.from_user.id

    try:
        paid_payment = await supabase.get_succeeded_payment_by_user_async(telegram_id)
        if paid_payment:
            await send_invite_link(callback, telegram, supabase, paid_payment["payment_id"])
            return

        if await answer_if_invite_already_sent(callback, supabase):
            return

        payment_id, payment_url = await yookassa.create_payment_async(telegram_id)
        await supabase.create_pending_payment_async(telegram_id, payment_id)
        await callback.message.answer(
            "Перейдите по ссылке для оплаты:\n"
            f"{payment_url}\n\n"
            "После оплаты вернитесь в бот и нажмите «Проверить оплату».",
            reply_markup=payment_keyboard(payment_url),
        )
    except InviteLinkError:
        logger.exception("Payment found but invite link creation failed for telegram_id=%s", telegram_id)
        await callback.message.answer(
            "Оплата найдена, но бот не смог создать ссылку в канал. Напишите: @a_vng"
        )
    except Exception:
        logger.exception("Failed to process access request for telegram_id=%s", telegram_id)
        await callback.message.answer(
            "Не удалось создать оплату. Попробуйте позже или напишите: @a_vng"
        )


@router.callback_query(lambda callback: callback.data == "check_payment")
async def check_payment(callback: CallbackQuery) -> None:
    await callback.answer()
    settings = get_settings()
    supabase = get_supabase_service()
    yookassa = get_yookassa_service()
    telegram = TelegramService(callback.bot, settings)

    telegram_id = callback.from_user.id

    try:
        paid_payment = await supabase.get_succeeded_payment_by_user_async(telegram_id)
        if paid_payment:
            await send_invite_link(callback, telegram, supabase, paid_payment["payment_id"])
            return

        if await answer_if_invite_already_sent(callback, supabase):
            return

        pending_payment = await supabase.get_latest_pending_payment_by_user_async(telegram_id)
        if not pending_payment:
            await callback.message.answer(
                "У вас нет ожидающего платежа. Нажмите «Получить доступ»."
            )
            return

        payment_id = pending_payment["payment_id"]
        payment = await yookassa.get_payment_async(payment_id)
        if getattr(payment, "status", None) != "succeeded":
            await callback.message.answer(
                "Оплата пока не найдена. Если вы уже оплатили, подождите немного "
                "и нажмите «Проверить оплату» еще раз."
            )
            return

        await supabase.mark_payment_succeeded_async(payment_id)
        await send_invite_link(callback, telegram, supabase, payment_id)
    except InviteLinkError:
        logger.exception("Payment found but invite link creation failed for telegram_id=%s", telegram_id)
        await callback.message.answer(
            "Оплата найдена, но бот не смог создать ссылку в канал. Напишите: @a_vng"
        )
    except Exception:
        logger.exception("Failed to check payment for telegram_id=%s", telegram_id)
        await callback.message.answer(
            "Не удалось проверить оплату. Попробуйте позже или напишите: @a_vng"
        )
