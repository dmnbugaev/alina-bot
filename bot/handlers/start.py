from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import start_keyboard

router = Router()

START_TEXT = (
    "Получить доступ\n"
    "- Оплатить подписку\n"
    "- После оплаты вернуться в бот и нажать «Проверить оплату»\n"
    "- После проверки бот выдаст одноразовую ссылку-приглашение в закрытый канал"
)


@router.message(CommandStart())
async def start_command(message: Message) -> None:
    await message.answer(START_TEXT, reply_markup=start_keyboard())


@router.callback_query(lambda callback: callback.data == "contact_me")
async def contact_me(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("По всем вопросам: @a_vng")
