from pathlib import Path
from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.crud import transaction as transaction_crud


router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / 'templates')
def format_amount(value):
    return f"{value:,.2f}"

templates.env.filters["amount"] = format_amount

@router.get("/transactions")
def transaction_list(request: Request, db: Session = Depends(get_db)):
    transactions = transaction_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="transactions/list.html",
        context={"transactions": transactions}
    )

@router.get("/transactions/rows")
def transaction_rows(
    request: Request,
    db: Session = Depends(get_db),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    transaction_type: str = Query(default="")
):
    from datetime import date
    from balance360.enums import TransactionType

    date_from_parsed = date.fromisoformat(date_from) if date_from else None
    date_to_parsed = date.fromisoformat(date_to) if date_to else None
    type_parsed = TransactionType(transaction_type) if transaction_type else None

    transactions = transaction_crud.get_all(
        db,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
        transaction_type=type_parsed
    )
    return templates.TemplateResponse(
        request=request,
        name="transactions/rows.html",
        context={"transactions": transactions}
    )
