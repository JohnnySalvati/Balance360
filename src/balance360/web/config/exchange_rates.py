import uuid
import datetime
import json
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from balance360.dependencies import get_db
from balance360.models.exchange_rate import ExchangeRate
from balance360.schemas.exchange_rate import ExchangeRateCreate
from balance360.services.rate_sync import sync_all
from balance360.crud import currency as currency_crud
from balance360.crud import exchange_rate as exchange_rate_crud
from balance360.web.templating import templates

router = APIRouter(prefix="/exchange-rates")

def _get_rates_by_currency(db: Session) -> list[dict]:
    currencies = currency_crud.get_all(db)

    groups = []
    for currency in sorted(currencies, key=lambda c: c.name):
        rates = db.execute(
            select(ExchangeRate)
            .where(ExchangeRate.currency_id == currency.id)
            .order_by(ExchangeRate.date.desc())
            .limit(60)
        ).scalars().all()
        groups.append({"currency": currency, "rates": rates})

    return groups


@router.get("/", response_class=HTMLResponse)
def exchange_rates_page(request: Request, db: Session = Depends(get_db)):
    groups = _get_rates_by_currency(db)
    currencies = currency_crud.get_all(db)

    return templates.TemplateResponse(
        request=request,
        name="config/exchange_rates/exchange_rates.html",
        context={"groups": groups, "currencies": currencies, "today": datetime.date.today()},
    )


@router.post("/", response_class=HTMLResponse)
def create_exchange_rate(
    request: Request,
    db: Session = Depends(get_db),
    currency_id: str = Form(...),
    date: str = Form(...),
    rate: str = Form(...),
):
    data = ExchangeRateCreate(
        currency_id=uuid.UUID(currency_id),
        date=datetime.date.fromisoformat(date),
        rate=Decimal(rate),
    )
    exchange_rate_crud.create(db, data)

    groups = _get_rates_by_currency(db)

    return templates.TemplateResponse(
        request=request,
        name="config/exchange_rates/_rates_table.html",
        context={"groups": groups},
    )


@router.delete("/{exchange_rate_id}", response_class=HTMLResponse)
def delete_exchange_rate(
    request: Request,
    exchange_rate_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    rate = exchange_rate_crud.get_by_id(db, exchange_rate_id)
    if rate:
        exchange_rate_crud.delete(db, rate)

    groups = _get_rates_by_currency(db)

    return templates.TemplateResponse(
        request=request,
        name="config/exchange_rates/_rates_table.html",
        context={"groups": groups},
    )

@router.post("/sync", response_class=HTMLResponse)
def synchronize_all(
request: Request,
    db: Session = Depends(get_db),
):
    
    result = sync_all(db)
    
    groups = _get_rates_by_currency(db)
    
    response = templates.TemplateResponse(
        request=request,
        name="config/exchange_rates/_rates_table.html",
        context={"groups": groups,
                 "result": result
                 },
    )

    ok = result.get("ok", {})
    ok_message = " | ".join(f"{code}: {msg}" for code, msg in ok.items())
        
    errors = result.get("errors", {})
    error_message = " | ".join(f"{code}: {msg}" for code, msg in errors.items())

    message = " || ".join(p for p in (ok_message, error_message) if p)

    response.headers["HX-Trigger"] = json.dumps({"showToast": {
        "message": message,
        "type": "error" if errors else "success"
        }})
        
    return response
