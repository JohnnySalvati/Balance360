from sqlalchemy import select, func
from balance360.models.exchange_rate import ExchangeRate

def ars_rate_subquery(source_currency_id, source_date, target_currency_id, target_date):
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
