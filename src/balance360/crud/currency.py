import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.currency import Currency
from balance360.models.exchange_rate import ExchangeRate
from balance360.models.account import Account
from balance360.schemas.currency import CurrencyCreate, CurrencyUpdate
from balance360.exceptions import CurrencyDeleteError

def get_all(db: Session, search: str|None=None) -> list[Currency]:
    stmt = select(Currency)

    if search:
        stmt = stmt.where(Currency.name.ilike(f"%{search}%"))

    stmt = stmt.order_by(Currency.name)
    
    currencies = db.execute(stmt).scalars().all()
    return list(currencies)

def get_by_id(db: Session, currency_id: uuid.UUID) -> Currency | None:
    currency = db.execute(select(Currency).where(Currency.id == currency_id)).scalars().first()
    return currency

def get_by_code(db: Session, currency_code: str) -> Currency|None:
    currency = db.execute(select(Currency).where(Currency.code == currency_code)).scalars().first()
    return currency

def create(db: Session, data: CurrencyCreate) -> Currency:
    db_currency = Currency(**data.model_dump())
    db.add(db_currency)
    db.flush()
    db.refresh(db_currency)
    return db_currency

def delete(db: Session, currency: Currency):
    stmt = (select(Account).where(Account.currency_id == currency.id).limit(1))
    accounts = db.execute(stmt).scalar()
    
    stmt = (select(ExchangeRate).where(ExchangeRate.currency_id == currency.id).limit(1))
    exchange_rates = db.execute(stmt).scalar()

    if accounts or exchange_rates:
        raise CurrencyDeleteError("No se puede borrar: tiene cuentas o cotizaciones asociadas")
    db.delete(currency)
    db.flush()

def update(db: Session, currency: Currency, data: CurrencyUpdate) -> Currency:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(currency, field, value)
    db.flush()
    db.refresh(currency)
    return currency

def get_exchange_rates(db: Session, currency: Currency) -> list[ExchangeRate]:
    exchange_rates = db.execute(select(ExchangeRate).where(ExchangeRate.currency_id == currency.id)).scalars().all()
    return list(exchange_rates)
