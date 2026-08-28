from decimal import Decimal

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def format_price(amount: Decimal) -> str:
    return f"{amount:,.2f}".replace(",", " ").replace(".00", "")


def start_keyboard(amount: Decimal) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Получить доступ — {format_price(amount)} ₽",
                    callback_data="get_access",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Связаться со мной",
                    callback_data="contact_me",
                )
            ],
        ]
    )


def payment_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=payment_url)],
            [
                InlineKeyboardButton(
                    text="Проверить оплату",
                    callback_data="check_payment",
                )
            ],
        ]
    )
