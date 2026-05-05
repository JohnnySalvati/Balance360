import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.currency import ExchangeRate
from balance360.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateUpdate

def get_all(db: Session) -> list[ExchangeRate]:
    exchange_rates = db.execute(select(ExchangeRate)).scalars().all()
    return list(exchange_rates)

def get_by_id(db: Session, exchange_rate_id: uuid.UUID) -> ExchangeRate|None:
    exchange_rate = db.execute(select(ExchangeRate).where(ExchangeRate.id == exchange_rate_id)).scalars().first()
    return exchange_rate

def create(db: Session, data: ExchangeRateCreate):
    db_exchange_rate = ExchangeRate(**data.model_dump())
    db.add(db_exchange_rate)
    db.commit()
    db.refresh(db_exchange_rate)
    return db_exchange_rate

def delete(db: Session, exchange_rate: ExchangeRate):
    db.delete(exchange_rate)
    db.commit()

def update(db: Session, exchange_rate: ExchangeRate, data: ExchangeRateUpdate) -> ExchangeRate:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(exchange_rate, field, value)
    db.commit()
    db.refresh(exchange_rate)
    return exchange_rate
