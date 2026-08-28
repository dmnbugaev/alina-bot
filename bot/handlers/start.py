import logging
import re

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.keyboards.inline import format_price, start_keyboard
from bot.services.factory import get_supabase_service

logger = logging.getLogger(__name__)
router = Router()

SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def normalize_source(value: str | None) -> str:
    return value if value and SOURCE_PATTERN.fullmatch(value) else "organic"


@router.message(CommandStart())
async def start_command(message: Message, command: CommandObject) -> None:
    settings = get_settings()
    source = normalize_source(command.args)
    if message.from_user:
        try:
            supabase = get_supabase_service()
            await supabase.record_user_async(message.from_user.id, source)
            await supabase.record_event_async(
                message.from_user.id,
                "start",
                source,
            )
        except Exception:
            logger.exception("Failed to record /start analytics")

    text = (
        "Закрытый канал Алины\n\n"
        "Эксклюзивный контент, которого нет в открытом доступе.\n\n"
        f"• Разовый доступ — {format_price(settings.payment_amount)} ₽\n"
        "• Без подписки и автоматических списаний\n"
        "• После оплаты бот автоматически пришлёт персональную ссылку\n\n"
        "Нажмите кнопку ниже, чтобы получить доступ."
    )
    await message.answer(text, reply_markup=start_keyboard(settings.payment_amount))


@router.callback_query(lambda callback: callback.data == "contact_me")
async def contact_me(callback: CallbackQuery) -> None:
    await callback.answer()
    settings = get_settings()
    try:
        await get_supabase_service().record_event_async(
            callback.from_user.id,
            "support_clicked",
        )
    except Exception:
        logger.exception("Failed to record support click")
    if callback.message:
        await callback.message.answer(
            f"По всем вопросам: {settings.support_username}",
        )
