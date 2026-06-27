import uuid
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from balance360.models.exchange_rate import ExchangeRate
from balance360.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateUpdate

def get_all(db: Session) -> list[ExchangeRate]:
    exchange_rates = db.execute(select(ExchangeRate)).scalars().all()
    return list(exchange_rates)

def get_by_id(db: Session, exchange_rate_id: uuid.UUID) -> ExchangeRate|None:
    exchange_rate = db.execute(select(ExchangeRate).where(ExchangeRate.id == exchange_rate_id)).scalars().first()
    return exchange_rate

def get_by_currency_and_date(db: Session, currency_id: uuid.UUID, date: date) -> ExchangeRate|None:
    exchange_rate = db.execute(select(ExchangeRate).where(ExchangeRate.currency_id == currency_id, ExchangeRate.date == date)).scalars().first()
    return exchange_rate

def create(db: Session, data: ExchangeRateCreate):
    db_exchange_rate = ExchangeRate(**data.model_dump())
    db.add(db_exchange_rate)
    db.flush()
    db.refresh(db_exchange_rate)
    return db_exchange_rate

def delete(db: Session, exchange_rate: ExchangeRate):
    db.delete(exchange_rate)
    db.flush()

def update(db: Session, exchange_rate: ExchangeRate, data: ExchangeRateUpdate) -> ExchangeRate:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(exchange_rate, field, value)
    db.flush()
    db.refresh(exchange_rate)
    return exchange_rate


def upsert(db: Session, data: ExchangeRateCreate) -> ExchangeRate: 
    stmt = insert(ExchangeRate).values(**data.model_dump())
    constraint = "uq_exchange_rate"
    set_ = {"rate": data.rate}
    stmt = stmt.on_conflict_do_update(constraint=constraint, set_=set_)
    stmt = stmt.returning(ExchangeRate)
    return db.execute(stmt).scalars().one()
