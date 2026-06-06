from sqlalchemy import select
from balance360.models.exchange_rate import ExchangeRate

def ars_rate_subquery(currency_id, date):
    return (
        select(ExchangeRate.rate)
        .where(ExchangeRate.currency_id == currency_id)
        .where(ExchangeRate.date <= date)
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    ).scalar_subquery()
