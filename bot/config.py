from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
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
    supabase_service_role_key: str | None = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    telegram_webhook_secret: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET")
    payment_amount: str = Field(default="990.00", alias="PAYMENT_AMOUNT")
    payment_currency: str = Field(default="RUB", alias="PAYMENT_CURRENCY")
    payment_description: str = Field(
        default="Единоразовый доступ в приватный Telegram-канал",
        alias="PAYMENT_DESCRIPTION",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
