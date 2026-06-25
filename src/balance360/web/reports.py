from uuid import UUID
from datetime import date
from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, extract, and_
from balance360.models.user import User
from balance360.models.transaction import Transaction
from balance360.models.account import Account
from balance360.models.category import Category
from balance360.crud import entity as entity_crud
from balance360.services.exchange_rate import ars_rate_subquery
from balance360.services.period import resolve_period
from balance360.reports import get_account_balances, build_category_tree, get_iva_position, get_tributes, get_iibb_on_sales, get_invoice_profit
from balance360.web.templating import templates
from balance360.dependencies import get_current_user, get_db
from balance360.enums import TransactionType

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

router = APIRouter(prefix="/reports")

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
                func.sum(
                    Transaction.amount * func.coalesce(ars_rate_subquery(Account.currency_id, Transaction.date), 1)
                )
                .filter(
                    Transaction.type == TransactionType.income,
                    Transaction.is_transfer == False
                ), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(
                    Transaction.amount * func.coalesce(ars_rate_subquery(Account.currency_id, Transaction.date), 1)
                )
                .filter(
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



@router.get("/pl")
def report_pl(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    year: str = Query(default=""),
    month: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    entity_id: str = Query(default=""),
):
    start, end = resolve_period(
        year=int(year) if year else None,
        month=int(month) if month else None,
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
    )

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]
   

    stmt = (
        select(
            extract("year", Transaction.date).label("year"),
            extract("month", Transaction.date).label("month"),
            func.coalesce(
                func.sum(
                    Transaction.amount * func.coalesce(ars_rate_subquery(Account.currency_id, Transaction.date),1)
                    ).filter(Transaction.type == TransactionType.income), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(
                    Transaction.amount *func.coalesce(ars_rate_subquery(Account.currency_id, Transaction.date), 1)
                    ).filter(Transaction.type == TransactionType.expense), 0
            ).label("total_expense"),
        )
        .where(Transaction.is_transfer == False)
        .where(Transaction.date >= start)
        .where(Transaction.date <= end)
        .where(Transaction.entity_id.in_(entity_ids))
        .join(Account)
        .group_by("year", "month")
        .order_by("year", "month")
    )
    
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
            "start": start,
            "end": end,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "year": year,
            "month": month,
            "date_from": date_from,
            "date_to": date_to,
            "months": months_data
        },
    )


@router.get("/pl/category")
def report_pl_category(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    year: str = Query(default=""),
    month: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    entity_id: str = Query(default=""),
):
    start, end = resolve_period(
        year=int(year) if year else None,
        month=int(month) if month else None,
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
    )

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]
   
    tx_conditions = [
        Transaction.category_id == Category.id,
        Transaction.is_transfer == False,
        Transaction.date >= start,
        Transaction.date <= end,
        Transaction.entity_id.in_(entity_ids)
    ]

    stmt = (
        select(
            Category,
            func.coalesce(
                func.sum(
                    Transaction.amount * func.coalesce(ars_rate_subquery(Account.currency_id, Transaction.date), 1)
                ).filter(Transaction.type == TransactionType.income), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(
                    Transaction.amount * func.coalesce(ars_rate_subquery(Account.currency_id, Transaction.date), 1)
                ).filter(Transaction.type == TransactionType.expense), 0
            ).label("total_expense"),
        )
        .outerjoin(Transaction, and_(*tx_conditions))
        .outerjoin(Account, Account.id == Transaction.account_id)
        .group_by(Category.id)
        .order_by(func.sum(Transaction.amount).desc())
    )

    rows = db.execute(stmt).all()
    
    groups_data = build_category_tree(list(rows))

    return templates.TemplateResponse(
        request=request,
        name="reports/pl_category.html",
        context={
            "groups": groups_data,
            "start": start,
            "end": end,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "year": year,
            "month": month,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@router.get("/net-worth")
def report_net_worth(
    request: Request,
    db: Session = Depends(get_db),
):
    rows_data = get_account_balances(db)

    total_ars = sum(r["ars_balance"] for r in rows_data)
    
    return templates.TemplateResponse(
        request=request,
        name="reports/net_worth.html",
        context={
            "accounts": rows_data,
            "total_ars": total_ars
            }
    )


@router.get("/iva")
def iva_report(
    request: Request,
    year: str = Query(default=""),
    month: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    start, end = resolve_period(
        year=int(year) if year else None,
        month=int(month) if month else None,
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
    )

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    iva = get_iva_position(db, start, end, entity_ids)

    return templates.TemplateResponse(
        request=request,
        name="reports/iva.html",
        context={
            "iva": iva, 
            "start": start,
            "end": end,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "year": year,
            "month": month,
            "date_from": date_from,
            "date_to": date_to
        }
    )


@router.get("/tributes")
def tribute_report(
    request: Request,
    year: str = Query(default=""),
    month: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    start, end = resolve_period(
        year=int(year) if year else None,
        month=int(month) if month else None,
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
    )

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    tributes = get_tributes(db, start, end, entity_ids)

    return templates.TemplateResponse(
        request=request,
        name="reports/tributes.html",
        context={
            "tributes": tributes, 
            "start": start,
            "end": end,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "year": year,
            "month": month,
            "date_from": date_from,
            "date_to": date_to
        }
    )


@router.get("/iibb")
def iibb_report(
    request: Request,
    year: str = Query(default=""),
    month: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    start, end = resolve_period(
        year=int(year) if year else None,
        month=int(month) if month else None,
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
    )

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    iibb_by_entity = get_iibb_on_sales(db, start, end, entity_ids)

    return templates.TemplateResponse(
        request=request,
        name="reports/iibb.html",
        context={
            "iibb_by_entity": iibb_by_entity, 
            "start": start,
            "end": end,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "year": year,
            "month": month,
            "date_from": date_from,
            "date_to": date_to
        }
    )



@router.get("/profit")
def profit_report(
    request: Request,
    year: str = Query(default=""),
    month: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    start, end = resolve_period(
        year=int(year) if year else None,
        month=int(month) if month else None,
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
    )

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    profit_by_entity = get_invoice_profit(db, start, end, entity_ids)

    return templates.TemplateResponse(
        request=request,
        name="reports/profit.html",
        context={
            "profit": profit_by_entity, 
            "start": start,
            "end": end,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "year": year,
            "month": month,
            "date_from": date_from,
            "date_to": date_to
        }
    )








