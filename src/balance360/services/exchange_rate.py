from uuid import UUID
from datetime import date
from sqlalchemy import select, func
from balance360.models.exchange_rate import ExchangeRate
from balance360.models.currency import Currency

def ars_rate_subquery(source_currency_id: UUID|None, source_date: date, target_currency_id: UUID|None, target_date: date):
    source = (
        select(ExchangeRate.rate)
        .where(ExchangeRate.currency_id == source_currency_id)
        .where(ExchangeRate.date <= source_date)
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    ).scalar_subquery()

    target = (
        select(ExchangeRate.rate)
        .where(ExchangeRate.currency_id == target_currency_id)
        .where(ExchangeRate.date <= target_date)
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    ).scalar_subquery()

    return (func.coalesce(source,1) / func.coalesce(target, 1))


def conversion_factor(source_id, txn_date, target_currency, reference_date):
    if not target_currency:
        result = ars_rate_subquery(source_id, txn_date, None, txn_date)
    elif target_currency.is_index:
        result = (ars_rate_subquery(source_id, txn_date, None, txn_date) *
                  ars_rate_subquery(target_currency.id, reference_date, target_currency.id, txn_date)
        )
    else:
        result = ars_rate_subquery(source_id, txn_date, target_currency.id, txn_date)

    return result