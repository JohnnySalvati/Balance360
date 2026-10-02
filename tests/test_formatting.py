import datetime
from decimal import Decimal

import pytest

from balance360.web.templating import format_amount, format_date, templates


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


@pytest.mark.parametrize(
    "value, expected",
    [
        (datetime.date(2026, 4, 7), "07/04/2026"),
        (datetime.date(2026, 12, 31), "31/12/2026"),
        # Una fecha opcional (vto. de pago, fulfilled_at) no tiene que romper la fila.
        (None, ""),
    ],
)
def test_format_date_argentine(value, expected):
    """Impresa sola, una `date` sale en ISO y en una lista eso se lee al reves."""
    assert format_date(value) == expected


def test_date_filter_is_registered():
    assert templates.env.filters["date"](datetime.date(2026, 4, 7)) == "07/04/2026"
