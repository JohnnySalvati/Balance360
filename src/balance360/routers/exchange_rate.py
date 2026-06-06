import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.models.exchange_rate import ExchangeRate
from balance360.schemas.exchange_rate import ExchangeRateRead, ExchangeRateUpdate, ExchangeRateCreate
from balance360.crud.exchange_rate import get_all, get_by_id, create, delete, update

router = APIRouter(prefix="/exchange_rates", tags=["exchange_rates"])

def get_exchange_rate_or_404(exchange_rate_id: uuid.UUID, db: Session = Depends(get_db)) -> ExchangeRate:
    exchange_rate = get_by_id(db, exchange_rate_id)
    if exchange_rate is None:
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    return exchange_rate

@router.get("/", response_model=list[ExchangeRateRead])
def list_exchange_rates(db: Session = Depends(get_db)):
    return get_all(db)

@router.get("/{exchange_rate_id}", response_model=ExchangeRateRead)
def get_exchange_rate(exchange_rate: ExchangeRate = Depends(get_exchange_rate_or_404)):
    return exchange_rate

@router.post("/", response_model=ExchangeRateRead)
def create_exchange_rate(data: ExchangeRateCreate, db: Session = Depends(get_db)):
    return create(db, data)

@router.delete("/{exchange_rate_id}", status_code=204)
def delete_exchange_rate(exchange_rate: ExchangeRate = Depends(get_exchange_rate_or_404), db: Session = Depends(get_db)):
    delete(db, exchange_rate)

@router.patch("/{exchange_rate_id}", response_model=ExchangeRateRead)
def update_exchange_rate(data: ExchangeRateUpdate, exchange_rate: ExchangeRate = Depends(get_exchange_rate_or_404), db: Session = Depends(get_db)):
    return update(db, exchange_rate, data)