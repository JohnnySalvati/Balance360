import uuid
from decimal import Decimal
import datetime
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select
from balance360.dependencies import get_db
from balance360.crud import currency as currency_crud
from balance360.crud import exchange_rate as exchange_rate_crud
from balance360.schemas.exchange_rate import ExchangeRateCreate
from balance360.models.exchange_rate import ExchangeRate

router = APIRouter(prefix="/exchange-rates")
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")


def format_amount(value):
    return f"{value:,.2f}"


templates.env.filters["amount"] = format_amount


def _get_rates_by_currency(db: Session) -> list[dict]:
    currencies = currency_crud.get_all(db)
    groups = []
    for currency in sorted(currencies, key=lambda c: c.name):
        rates = db.execute(
            select(ExchangeRate)
            .where(ExchangeRate.currency_id == currency.id)
            .order_by(ExchangeRate.date.desc())
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
