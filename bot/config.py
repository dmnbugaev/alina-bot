from decimal import Decimal, InvalidOperation
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    channel_id: str = Field(alias="CHANNEL_ID")
    yookassa_shop_id: str = Field(alias="YOOKASSA_SHOP_ID")
    yookassa_secret_key: str = Field(alias="YOOKASSA_SECRET_KEY")
    yookassa_return_url: str = Field(alias="YOOKASSA_RETURN_URL")
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_key: str = Field(alias="SUPABASE_KEY")
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    telegram_webhook_secret: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET")
    payment_amount: Decimal = Field(default=Decimal("990.00"), alias="PAYMENT_AMOUNT")
    payment_currency: str = Field(default="RUB", alias="PAYMENT_CURRENCY")
    payment_description: str = Field(
        default="Единоразовый доступ в приватный Telegram-канал",
        alias="PAYMENT_DESCRIPTION",
    )
    support_username: str = Field(default="@a_vng", alias="SUPPORT_USERNAME")
    admin_telegram_ids: str = Field(default="", alias="ADMIN_TELEGRAM_IDS")
    auto_fulfillment_enabled: bool = Field(default=False, alias="AUTO_FULFILLMENT_ENABLED")
    reminders_enabled: bool = Field(default=False, alias="REMINDERS_ENABLED")
    payment_poll_interval_seconds: int = Field(default=30, alias="PAYMENT_POLL_INTERVAL_SECONDS")
    payment_poll_batch_size: int = Field(default=20, alias="PAYMENT_POLL_BATCH_SIZE")
    invite_ttl_hours: int = Field(default=24, alias="INVITE_TTL_HOURS")
    reminder_delays_hours: str = Field(default="1,24", alias="REMINDER_DELAYS_HOURS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("telegram_webhook_secret", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("payment_amount", mode="before")
    @classmethod
    def validate_payment_amount(cls, value: str | Decimal) -> Decimal:
        try:
            amount = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("PAYMENT_AMOUNT must be a decimal number") from exc
        if amount <= 0:
            raise ValueError("PAYMENT_AMOUNT must be positive")
        return amount.quantize(Decimal("0.01"))

    @field_validator("payment_currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        currency = value.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("PAYMENT_CURRENCY must be a three-letter currency code")
        return currency

    @field_validator("support_username")
    @classmethod
    def normalize_support_username(cls, value: str) -> str:
        username = value.strip()
        return username if username.startswith("@") else f"@{username}"

    @field_validator("payment_poll_interval_seconds")
    @classmethod
    def validate_poll_interval(cls, value: int) -> int:
        if not 10 <= value <= 3600:
            raise ValueError("PAYMENT_POLL_INTERVAL_SECONDS must be between 10 and 3600")
        return value

    @field_validator("payment_poll_batch_size", "invite_ttl_hours")
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Value must be positive")
        return value

    @property
    def admin_ids(self) -> frozenset[int]:
        if not self.admin_telegram_ids.strip():
            return frozenset()
        try:
            return frozenset(
                int(item.strip()) for item in self.admin_telegram_ids.split(",") if item.strip()
            )
        except ValueError as exc:
            raise ValueError("ADMIN_TELEGRAM_IDS must contain comma-separated integers") from exc

    @property
    def reminder_hours(self) -> tuple[int, int]:
        try:
            values = tuple(int(item.strip()) for item in self.reminder_delays_hours.split(","))
        except ValueError as exc:
            raise ValueError("REMINDER_DELAYS_HOURS must contain two integers") from exc
        if len(values) != 2 or values[0] <= 0 or values[1] <= values[0]:
            raise ValueError("REMINDER_DELAYS_HOURS must contain two increasing positive integers")
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()
