import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from balance360.models.currency import Currency
from balance360.schemas.currency import CurrencyRead, CurrencyCreate, CurrencyUpdate
from balance360.schemas.exchange_rate import ExchangeRateRead
from balance360.crud.currency import get_all, get_by_id, create, delete, update, get_exchange_rates
from balance360.dependencies import get_db

router = APIRouter(prefix="/currencies", tags=["currencies"])

def get_currency_or_404(currency_id: uuid.UUID, db: Session = Depends(get_db)) -> Currency:
    currency = get_by_id(db, currency_id)
    if currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    return currency

@router.get("/", response_model=list[CurrencyRead])
def list_currencies(db: Session = Depends(get_db)):
    return get_all(db)

@router.get("/{currency_id}", response_model=CurrencyRead)
def get_currency(currency: Currency = Depends(get_currency_or_404)):
    return currency

@router.post("/", response_model=CurrencyRead)
def create_currency(data: CurrencyCreate, db: Session = Depends(get_db)):
    return create(db, data)

@router.delete("/{currency_id}", status_code=204)
def delete_currency(currency: Currency = Depends(get_currency_or_404), db: Session = Depends(get_db)):
    delete(db, currency)

@router.patch("/{currency_id}", response_model=CurrencyRead)
def update_currency(data: CurrencyUpdate, currency: Currency = Depends(get_currency_or_404), db: Session = Depends(get_db)):
    return update(db, currency, data)

@router.get("/{currency_id}/exchange_rates", response_model=list[ExchangeRateRead])
def get_currency_exchange_rates(currency: Currency = Depends(get_currency_or_404), db: Session = Depends(get_db)):
    currency_exchange_rates = get_exchange_rates(db, currency)
    return list(currency_exchange_rates)