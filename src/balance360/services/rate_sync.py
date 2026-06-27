import httpx
import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from balance360.schemas.exchange_rate import ExchangeRateCreate
from balance360.crud import currency as currency_crud
from balance360.crud import exchange_rate as exchange_rate_crud
from balance360.exceptions import SyncServiceError

def sync_blue(db: Session):

    with httpx.Client(timeout=5) as client:
        response = client.get("https://dolarapi.com/v1/dolares/blue").raise_for_status()
        dolarapi = response.json()

    usd_currency = currency_crud.get_by_code(db, "USD")
    if not usd_currency:
        raise SyncServiceError("Moneda USD no encontrada")
    
    date = datetime.date.today().replace(day=1)

    rate = Decimal(str(dolarapi["venta"]))

    return exchange_rate_crud.upsert(db, ExchangeRateCreate(currency_id=usd_currency.id, date=date, rate=rate))

    



