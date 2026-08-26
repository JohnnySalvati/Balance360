from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, extract, func, select
from sqlalchemy.orm import Session

from balance360.crud import currency as currency_crud
from balance360.crud import entity as entity_crud
from balance360.dependencies import Period, get_current_user, get_db, get_period
from balance360.enums import TransactionType
from balance360.models.account import Account
from balance360.models.category import Category
from balance360.models.transaction import Transaction
from balance360.models.user import User
from balance360.reports import (
    build_category_tree,
    get_account_balances,
    get_iibb_on_sales,
    get_invoice_profit,
    get_iva_position,
    get_monthly_evolution,
    get_tributes,
)
from balance360.services.exchange_rate import conversion_factor
from balance360.web.templating import templates

MONTH_NAMES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

router = APIRouter(prefix="/reports")


@router.get("")
def reports_index(request: Request):
    return templates.TemplateResponse(request=request, name="reports/index.html", context={})


@router.get("/balance")
def report_balance(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    currency_id: str = Query(default=""),
    entity_id: str = Query(default=""),
):
    to_currency = currency_crud.get_by_id(db, UUID(currency_id)) if currency_id else None

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    stmt = (
        select(
            Account,
            func.coalesce(
                func.sum(
                    Transaction.amount
                    * conversion_factor(
                        source_id=Account.currency_id,
                        txn_date=Transaction.date,
                        target_currency=to_currency,
                        reference_date=date.today(),
                    )
                ).filter(
                    Transaction.entity_id.in_(entity_ids),
                    Transaction.type == TransactionType.income,
                    Transaction.is_transfer.is_(False),
                ),
                0,
            ).label("total_income"),
            func.coalesce(
                func.sum(
                    Transaction.amount
                    * conversion_factor(
                        source_id=Account.currency_id,
                        txn_date=Transaction.date,
                        target_currency=to_currency,
                        reference_date=date.today(),
                    )
                ).filter(
                    Transaction.entity_id.in_(entity_ids),
                    Transaction.type == TransactionType.expense,
                    Transaction.is_transfer.is_(False),
                ),
                0,
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
        if row.total_income != 0 or row.total_expense != 0
    ]

    return templates.TemplateResponse(
        request=request,
        name="reports/balance.html",
        context={
            "accounts": accounts_data,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "currencies": currency_crud.get_all(db),
            "selected_currency_id": currency_id,
        },
    )


@router.get("/pl")
def report_pl(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    period: Period = Depends(get_period),
    entity_id: str = Query(default=""),
    currency_id: str = Query(default=""),
):
    to_currency = currency_crud.get_by_id(db, UUID(currency_id)) if currency_id else None

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    stmt = (
        select(
            extract("year", Transaction.date).label("year"),
            extract("month", Transaction.date).label("month"),
            func.coalesce(
                func.sum(
                    Transaction.amount
                    * conversion_factor(
                        source_id=Account.currency_id,
                        txn_date=Transaction.date,
                        target_currency=to_currency,
                        reference_date=date.today(),
                    )
                ).filter(Transaction.type == TransactionType.income),
                0,
            ).label("total_income"),
            func.coalesce(
                func.sum(
                    Transaction.amount
                    * conversion_factor(
                        source_id=Account.currency_id,
                        txn_date=Transaction.date,
                        target_currency=to_currency,
                        reference_date=date.today(),
                    )
                ).filter(Transaction.type == TransactionType.expense),
                0,
            ).label("total_expense"),
        )
        .where(Transaction.is_transfer.is_(False))
        .where(Transaction.date >= period.start)
        .where(Transaction.date <= period.end)
        .where(Transaction.entity_id.in_(entity_ids))
        .join(Account)
        .group_by("year", "month")
        .order_by("year", "month")
    )

    rows = db.execute(stmt).all()
    months_data = [
        {
            "year": int(row.year),
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
            "period": period,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "months": months_data,
            "currencies": currency_crud.get_all(db),
            "selected_currency_id": currency_id,
        },
    )


@router.get("/pl/category")
def report_pl_category(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    period: Period = Depends(get_period),
    entity_id: str = Query(default=""),
    currency_id: str = Query(default=""),
):
    to_currency = currency_crud.get_by_id(db, UUID(currency_id)) if currency_id else None

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    tx_conditions = [
        Transaction.category_id == Category.id,
        Transaction.is_transfer.is_(False),
        Transaction.date >= period.start,
        Transaction.date <= period.end,
        Transaction.entity_id.in_(entity_ids),
    ]

    stmt = (
        select(
            Category,
            func.coalesce(
                func.sum(
                    Transaction.amount
                    * conversion_factor(
                        source_id=Account.currency_id,
                        txn_date=Transaction.date,
                        target_currency=to_currency,
                        reference_date=date.today(),
                    )
                ).filter(Transaction.type == TransactionType.income),
                0,
            ).label("total_income"),
            func.coalesce(
                func.sum(
                    Transaction.amount
                    * conversion_factor(
                        source_id=Account.currency_id,
                        txn_date=Transaction.date,
                        target_currency=to_currency,
                        reference_date=date.today(),
                    )
                ).filter(Transaction.type == TransactionType.expense),
                0,
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
            "period": period,
            "groups": groups_data,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "currencies": currency_crud.get_all(db),
            "selected_currency_id": currency_id,
        },
    )


@router.get("/net-worth", name="report_net_worth")
def report_net_worth(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    entity_id: str = Query(default=""),
    currency_id: str = Query(default=""),
):
    to_currency = currency_crud.get_by_id(db, UUID(currency_id)) if currency_id else None

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    rows_data = get_account_balances(db, entity_ids, to_currency)

    total_ars = sum(r["ars_balance"] for r in rows_data)

    return templates.TemplateResponse(
        request=request,
        name="reports/net_worth.html",
        context={
            "accounts": rows_data,
            "total_ars": total_ars,
            "selected_entity_id": entity_id,
            "entities": user_entities,
            "currencies": currency_crud.get_all(db),
            "selected_currency_id": currency_id,
        },
    )


@router.get("/iva")
def iva_report(
    request: Request,
    period: Period = Depends(get_period),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    currency_id: str = Query(default=""),
):
    to_currency = currency_crud.get_by_id(db, UUID(currency_id)) if currency_id else None

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    iva = get_iva_position(db, period.start, period.end, entity_ids, to_currency)

    return templates.TemplateResponse(
        request=request,
        name="reports/iva.html",
        context={
            "period": period,
            "iva": iva,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "currencies": currency_crud.get_all(db),
            "selected_currency_id": currency_id,
        },
    )


@router.get("/tributes")
def tribute_report(
    request: Request,
    period: Period = Depends(get_period),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    currency_id: str = Query(default=""),
):
    to_currency = currency_crud.get_by_id(db, UUID(currency_id)) if currency_id else None

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    tributes = get_tributes(db, period.start, period.end, entity_ids, to_currency)

    return templates.TemplateResponse(
        request=request,
        name="reports/tributes.html",
        context={
            "period": period,
            "tributes": tributes,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "currencies": currency_crud.get_all(db),
            "selected_currency_id": currency_id,
        },
    )


@router.get("/iibb")
def iibb_report(
    request: Request,
    period: Period = Depends(get_period),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    currency_id: str = Query(default=""),
):
    to_currency = currency_crud.get_by_id(db, UUID(currency_id)) if currency_id else None

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    iibb_by_entity = get_iibb_on_sales(db, period.start, period.end, entity_ids, to_currency)

    return templates.TemplateResponse(
        request=request,
        name="reports/iibb.html",
        context={
            "period": period,
            "iibb_by_entity": iibb_by_entity,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "currencies": currency_crud.get_all(db),
            "selected_currency_id": currency_id,
        },
    )


def get_evolution_period(
    year: str = Query(default=""),
    month: str = Query(default="all"),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
) -> Period:
    """Como get_period pero el mes arranca en "Todos".

    Un reporte de evolucion con el mes actual preseleccionado mostraria una sola
    columna, que es justo lo que no sirve. El resto del filtro funciona igual.
    """
    return get_period(year=year, month=month, date_from=date_from, date_to=date_to)


@router.get("/evolution")
def evolution_report(
    request: Request,
    period: Period = Depends(get_evolution_period),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    currency_id: str = Query(default=""),
):
    to_currency = currency_crud.get_by_id(db, UUID(currency_id)) if currency_id else None

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    evolution = get_monthly_evolution(
        db, period.start, period.end, entity_ids=entity_ids, to_currency=to_currency
    )

    return templates.TemplateResponse(
        request=request,
        name="reports/evolution.html",
        context={
            "period": period,
            "evolution": evolution,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "currencies": currency_crud.get_all(db),
            "selected_currency_id": currency_id,
        },
    )


@router.get("/profit")
def profit_report(
    request: Request,
    period: Period = Depends(get_period),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    currency_id: str = Query(default=""),
):
    to_currency = currency_crud.get_by_id(db, UUID(currency_id)) if currency_id else None

    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    profit_by_entity = get_invoice_profit(db, period.start, period.end, entity_ids, to_currency)

    return templates.TemplateResponse(
        request=request,
        name="reports/profit.html",
        context={
            "period": period,
            "profit": profit_by_entity,
            "entities": user_entities,
            "selected_entity_id": entity_id,
            "currencies": currency_crud.get_all(db),
            "selected_currency_id": currency_id,
        },
    )
