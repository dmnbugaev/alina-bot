import logging

from aiogram import Router
from aiogram.types import CallbackQuery

from bot.config import get_settings
from bot.keyboards.inline import payment_keyboard
from bot.services.factory import (
    get_payment_orchestrator,
    get_supabase_service,
)
from bot.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)
router = Router()


async def answer_existing_access(
    callback: CallbackQuery,
    telegram: TelegramService,
) -> bool:
    delivery = await get_supabase_service().get_access_delivery_by_user_async(
        callback.from_user.id,
    )
    if not delivery or delivery.get("status") != "delivered":
        return False
    if not callback.message:
        return True
    if await telegram.is_channel_member(callback.from_user.id):
        await callback.message.answer("У вас уже есть доступ к закрытому каналу.")
    else:
        await callback.message.answer(
            "Доступ уже выдавался. Для повторного входа напишите: "
            f"{get_settings().support_username}",
        )
    return True


@router.callback_query(lambda callback: callback.data == "get_access")
async def get_access(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.message:
        return
    settings = get_settings()
    supabase = get_supabase_service()
    orchestrator = get_payment_orchestrator()
    telegram = TelegramService(callback.bot, settings)
    telegram_id = callback.from_user.id

    try:
        if await answer_existing_access(callback, telegram):
            return
        source = "organic"
        try:
            source = await supabase.get_user_source_async(telegram_id)
            await supabase.record_event_async(
                telegram_id,
                "buy_clicked",
                source,
            )
        except Exception:
            logger.exception("Failed to record buy click analytics")
        latest_payment = await supabase.get_latest_payment_by_user_async(
            telegram_id,
        )
        if latest_payment and latest_payment.get("status") == "succeeded":
            result = await orchestrator.sync_payment(latest_payment, telegram)
            if result.status != "delivered":
                await callback.message.answer(
                    "Оплата найдена, но доступ пока не удалось отправить. "
                    f"Бот повторит попытку автоматически. Поддержка: {settings.support_username}",
                )
            return
        payment = await orchestrator.get_or_create_checkout(
            telegram_id,
            source,
        )
        payment_url = payment.get("confirmation_url")
        if not payment_url:
            raise RuntimeError("YooKassa did not return a confirmation URL")
        await callback.message.answer(
            "Ссылка на оплату готова.\n\n"
            "После оплаты ничего нажимать не обязательно — бот проверит платёж "
            "и обычно пришлёт доступ в течение двух минут.\n\n"
            "Кнопка «Проверить оплату» остаётся доступна на случай задержки.",
            reply_markup=payment_keyboard(str(payment_url)),
        )
    except Exception:
        logger.exception(
            "Failed to process access request for telegram_id=%s",
            telegram_id,
        )
        await callback.message.answer(
            "Не удалось подготовить оплату. Попробуйте позже или напишите: "
            f"{settings.support_username}",
        )


@router.callback_query(lambda callback: callback.data == "check_payment")
async def check_payment(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.message:
        return
    settings = get_settings()
    supabase = get_supabase_service()
    orchestrator = get_payment_orchestrator()
    telegram = TelegramService(callback.bot, settings)
    telegram_id = callback.from_user.id

    try:
        if await answer_existing_access(callback, telegram):
            return
        payment = await supabase.get_latest_payment_by_user_async(telegram_id)
        if not payment:
            await callback.message.answer(
                "У вас нет ожидающего платежа. Нажмите «Получить доступ».",
            )
            return
        if payment.get("status") == "canceled":
            await callback.message.answer(
                "Предыдущая ссылка на оплату больше не активна. "
                "Нажмите «Получить доступ», чтобы создать новую.",
            )
            return

        result = await orchestrator.sync_payment(payment, telegram)
        if result.status == "pending":
            await callback.message.answer(
                "Оплата пока не найдена. Если вы уже оплатили, подождите немного "
                "и попробуйте ещё раз.",
            )
        elif result.status == "canceled":
            await callback.message.answer(
                "Платёж отменён или истёк. Нажмите «Получить доступ», чтобы создать новый.",
            )
        elif result.status == "succeeded":
            await callback.message.answer(
                "Оплата найдена, но доступ пока не удалось отправить. "
                f"Бот повторит попытку автоматически. Поддержка: {settings.support_username}",
            )
    except Exception:
        logger.exception(
            "Failed to check payment for telegram_id=%s",
            telegram_id,
        )
        await callback.message.answer(
            "Не удалось проверить оплату. Попробуйте позже или напишите: "
            f"{settings.support_username}",
        )
