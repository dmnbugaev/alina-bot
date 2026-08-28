from decimal import Decimal

import pytest
from pydantic import ValidationError

from bot.handlers.start import normalize_source
from bot.keyboards.inline import format_price
from tests.conftest import make_settings


def test_settings_parse_admins_and_reminders():
    settings = make_settings(
        ADMIN_TELEGRAM_IDS="10, 20",
        REMINDER_DELAYS_HOURS="1,24",
    )

    assert settings.admin_ids == frozenset({10, 20})
    assert settings.reminder_hours == (1, 24)
    assert settings.payment_amount == Decimal("499.00")


@pytest.mark.parametrize("amount", ["0", "-1", "not-a-number"])
def test_settings_reject_invalid_amount(amount):
    with pytest.raises(ValidationError):
        make_settings(PAYMENT_AMOUNT=amount)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("campaign_1", "campaign_1"),
        ("warm-audience", "warm-audience"),
        ("bad source", "organic"),
        ("../admin", "organic"),
        (None, "organic"),
    ],
)
def test_normalize_source(raw, expected):
    assert normalize_source(raw) == expected


def test_format_price():
    assert format_price(Decimal("499.00")) == "499"
    assert format_price(Decimal("1499.50")) == "1 499.50"
