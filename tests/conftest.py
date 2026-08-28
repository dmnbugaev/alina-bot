from bot.config import Settings


def make_settings(**overrides):
    values = {
        "BOT_TOKEN": "123456:TEST_TOKEN",
        "CHANNEL_ID": "-1001234567890",
        "YOOKASSA_SHOP_ID": "shop",
        "YOOKASSA_SECRET_KEY": "secret",
        "YOOKASSA_RETURN_URL": "https://t.me/test_bot",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "anon",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role",
        "PAYMENT_AMOUNT": "499.00",
        "PAYMENT_CURRENCY": "RUB",
        "PAYMENT_DESCRIPTION": "Test access",
        "ADMIN_TELEGRAM_IDS": "10,20",
    }
    values.update(overrides)
    return Settings(**values)
