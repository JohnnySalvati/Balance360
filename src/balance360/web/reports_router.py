from pathlib import Path
from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select, func, extract
from balance360.dependencies import get_db
from balance360.models.transaction import Transaction
from balance360.models.account import Account
from balance360.models.category import Category
from balance360.models.entity import Entity
from balance360.enums import TransactionType
from balance360.reports import group_by_parent
from balance360.crud import entity as entity_crud

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

router = APIRouter(prefix="/reports")
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def format_amount(value):
    return f"{value:,.2f}"

templates.env.filters["amount"] = format_amount


@router.get("")
def reports_index(request: Request):
    return templates.TemplateResponse(request=request, name="reports/index.html", context={})


@router.get("/balance")
def report_balance(request: Request, db: Session = Depends(get_db)):
    # Sum income and expenses per account, excluding transfers
    stmt = (
        select(
            Account,
            func.coalesce(
                func.sum(Transaction.amount).filter(
                    Transaction.type == TransactionType.income,
                    Transaction.is_transfer == False
                ), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(Transaction.amount).filter(
                    Transaction.type == TransactionType.expense,
                    Transaction.is_transfer == False
                ), 0
            ).label("total_expense"),
        )
        .outerjoin(Transaction, Transaction.account_id == Account.id)
        .group_by(Account.id)
        .order_by(Account.name)
    )
    rows = db.execute(stmt).all()

    accounts_data = [
        {
            "account": row.Account,
            "total_income": row.total_income,
            "total_expense": row.total_expense,
            "balance": row.total_income - row.total_expense,
        }
        for row in rows
    ]

    return templates.TemplateResponse(
        request=request,
        name="reports/balance.html",
        context={"accounts": accounts_data},
    )


def _apply_period_filters(stmt, year, date_from, date_to, month=None, entity_id=None):
    """Apply year, month, date range and entity filters to a statement."""
    if year:
        stmt = stmt.where(extract("year", Transaction.date) == year)
    if month:
        stmt = stmt.where(extract("month", Transaction.date) == month)
    if date_from:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.date <= date_to)
    if entity_id:
        stmt = stmt.where(Transaction.entity_id == entity_id)
    return stmt


@router.get("/pl")
def report_pl(
    request: Request,
    db: Session = Depends(get_db),
    year: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    entity_id: str = Query(default=""),
):
    from datetime import date
    from uuid import UUID

    years_stmt = (
        select(extract("year", Transaction.date).label("year"))
        .distinct()
        .order_by("year")
    )
    available_years = [int(r.year) for r in db.execute(years_stmt).all()]
    selected_year = int(year) if year else (available_years[-1] if available_years else None)
    date_from_parsed = date.fromisoformat(date_from) if date_from else None
    date_to_parsed = date.fromisoformat(date_to) if date_to else None
    entity_id_parsed = UUID(entity_id) if entity_id else None
    entities = entity_crud.get_all(db)

    stmt = (
        select(
            extract("year", Transaction.date).label("year"),
            extract("month", Transaction.date).label("month"),
            func.coalesce(
                func.sum(Transaction.amount).filter(Transaction.type == TransactionType.income), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(Transaction.amount).filter(Transaction.type == TransactionType.expense), 0
            ).label("total_expense"),
        )
        .where(Transaction.is_transfer == False)
        .group_by("year", "month")
        .order_by("year", "month")
    )
    stmt = _apply_period_filters(stmt, selected_year, date_from_parsed, date_to_parsed, entity_id=entity_id_parsed)

    rows = db.execute(stmt).all()
    months_data = [
        {
            "month_name": MONTH_NAMES[int(row.month)],
            "total_income": row.total_income,
            "total_expense": row.total_expense,
            "net": row.total_income - row.total_expense,
        }
        for row in rows
    ]

    return templates.TemplateResponse(
        request=request,
        name="reports/pl.html",
        context={
            "months": months_data,
            "available_years": available_years,
            "selected_year": selected_year,
            "date_from": date_from,
            "date_to": date_to,
            "entities": entities,
            "selected_entity_id": entity_id,
        },
    )


@router.get("/pl/category")
def report_pl_category(
    request: Request,
    db: Session = Depends(get_db),
    year: str = Query(default=""),
    month: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    entity_id: str = Query(default=""),
):
    from datetime import date
    from uuid import UUID

    years_stmt = (
        select(extract("year", Transaction.date).label("year"))
        .distinct()
        .order_by("year")
    )
    available_years = [int(r.year) for r in db.execute(years_stmt).all()]
    selected_year = int(year) if year else (available_years[-1] if available_years else None)
    selected_month = int(month) if month else None
    date_from_parsed = date.fromisoformat(date_from) if date_from else None
    date_to_parsed = date.fromisoformat(date_to) if date_to else None
    entity_id_parsed = UUID(entity_id) if entity_id else None
    entities = entity_crud.get_all(db)

    stmt = (
        select(
            Category,
            func.coalesce(
                func.sum(Transaction.amount).filter(Transaction.type == TransactionType.income), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(Transaction.amount).filter(Transaction.type == TransactionType.expense), 0
            ).label("total_expense"),
        )
        .outerjoin(Transaction, Transaction.category_id == Category.id)
        .where(Transaction.is_transfer == False)
        .group_by(Category.id)
        .order_by(func.sum(Transaction.amount).desc())
    )
    stmt = _apply_period_filters(stmt, selected_year, date_from_parsed, date_to_parsed, selected_month, entity_id_parsed)

    rows = db.execute(stmt).all()
    
    groups_data = group_by_parent(rows)

    return templates.TemplateResponse(
        request=request,
        name="reports/pl_category.html",
        context={
            "groups": groups_data,
            "available_years": available_years,
            "selected_year": selected_year,
            "selected_month": selected_month,
            "date_from": date_from,
            "date_to": date_to,
            "month_names": MONTH_NAMES,
            "entities": entities,
            "selected_entity_id": entity_id,
        },
    )
