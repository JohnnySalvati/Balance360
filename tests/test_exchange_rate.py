import pytest
from decimal import Decimal
import datetime
from tests import factories
from balance360.schemas.exchange_rate import ExchangeRateCreate
from balance360.crud import exchange_rate as exchange_rate_crud

def test_insert_no_conflict(db):
    currency = factories.make_currency(db)
    date1 = datetime.date(day=1, month=1, year=2026)
    date2 = datetime.date(day=2, month=1, year=2026)
    
    exchange_rate_1 = factories.make_exchange_rate(db,
                                                currency_id=currency.id,
                                                date=date1,
                                                rate=Decimal(5)
                                                )
    data = ExchangeRateCreate(currency_id=currency.id, date=date2, rate=Decimal(15))

    exchange_rate_2 = exchange_rate_crud.upsert(db, data)

    db.expire_all()

    assert exchange_rate_1.rate == Decimal(5)
    assert exchange_rate_2.rate == Decimal(15)
    assert len(exchange_rate_crud.get_all(db)) == 2

def test_insert_with_conflict(db):
    currency = factories.make_currency(db)
    date1 = datetime.date(day=1, month=1, year=2026)
    date2 = datetime.date(day=1, month=1, year=2026)
    exchange_rate_1 = factories.make_exchange_rate(db,
                                                currency_id=currency.id,
                                                date=date1,
                                                rate=Decimal(5)
                                                )
    data = ExchangeRateCreate(currency_id=currency.id, date=date2, rate=Decimal(15))

    exchange_rate_2 = exchange_rate_crud.upsert(db, data)

    db.expire_all()

    assert exchange_rate_1.rate == Decimal(15)
    assert exchange_rate_2.rate == Decimal(15)
    assert len(exchange_rate_crud.get_all(db)) == 1

