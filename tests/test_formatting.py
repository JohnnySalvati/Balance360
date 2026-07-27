from decimal import Decimal

import pytest

from balance360.web.templating import format_amount, templates


@pytest.mark.parametrize(
    "value, expected",
    [
        (Decimal("1234567.89"), "1.234.567,89"),
        (Decimal("0.5"), "0,50"),
        (Decimal("-1234.5"), "-1.234,50"),
        # ROUND_HALF_UP: banker's rounding (HALF_EVEN) would give "0,12"
        (Decimal("0.125"), "0,13"),
    ],
)
def test_format_amount_argentine(value, expected):
    assert format_amount(value) == expected


def test_currency_filter_prefixes_symbol():
    assert templates.env.filters["currency"](Decimal("0.125")) == "$ 0,13"
