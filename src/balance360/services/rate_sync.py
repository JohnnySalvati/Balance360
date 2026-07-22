import datetime
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from balance360.crud import currency as currency_crud
from balance360.crud import exchange_rate as exchange_rate_crud
from balance360.exceptions import SyncServiceError
from balance360.schemas.exchange_rate import ExchangeRateCreate


def sync_blue(db: Session) -> int:
    return sync_series(
        db=db,
        url="https://api.argentinadatos.com/v1/cotizaciones/dolares/blue",
        currency_code="USD",
        extractor="venta",
    )


def sync_uva(db: Session) -> int:
    return sync_series(
        db=db,
        url="https://api.argentinadatos.com/v1/finanzas/indices/uva",
        currency_code="UVA",
        extractor="valor",
    )


def sync_series(db: Session, url: str, currency_code: str, extractor: str) -> int:

    with httpx.Client(timeout=50) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()

    currency = currency_crud.get_by_code(db, currency_code=currency_code)
    if not currency:
        raise SyncServiceError(f"Moneda {currency_code} no encontrada")

    updated = exchange_rate_crud.upsert_many(
        db,
        [
            ExchangeRateCreate(
                currency_id=currency.id,
                date=datetime.date.fromisoformat(row["fecha"]),
                rate=Decimal(str(row[extractor])),
            )
            for row in payload
        ],
    )

    return updated


def sync_all(db: Session) -> dict:
    ok = {}
    errors = {}
    try:
        with db.begin_nested():
            ok["uva"] = sync_uva(db)
    except Exception as e:
        errors["uva"] = str(e)

    try:
        with db.begin_nested():
            ok["usd"] = sync_blue(db)
    except Exception as e:
        errors["usd"] = str(e)

    return {"ok": ok, "errors": errors}
