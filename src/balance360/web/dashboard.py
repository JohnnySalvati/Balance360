import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from balance360.crud import entity_membership as entity_membership_crud
from balance360.dependencies import get_current_user, get_db
from balance360.models.user import User
from balance360.reports import (
    get_account_balances,
    get_expenses_by_category,
    get_monthly_income_expense,
    get_monthly_profit,
)
from balance360.web.templating import templates

router = APIRouter(prefix="/dashboard")


@router.get("")
def dashboard_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: str = Query(default=""),
):

    memberships = entity_membership_crud.get_by_user(db, current_user.id)
    entity_ids = [m.entity_id for m in memberships]
    entities = [m.entity for m in memberships]
    entity_id_parsed = uuid.UUID(entity_id) if entity_id else None

    if entity_id_parsed and entity_id_parsed in entity_ids:
        entity_ids = [entity_id_parsed]

    rows_data = get_account_balances(db, entity_ids)

    return templates.TemplateResponse(
        request=request,
        name="dashboard/index.html",
        context={
            "accounts": rows_data,
            "total_ars": sum(r["ars_balance"] for r in rows_data),
            "monthly": get_monthly_income_expense(db, months=12, entity_ids=entity_ids),
            "monthly_profit": get_monthly_profit(db, months=12, entity_ids=entity_ids),
            "by_category": get_expenses_by_category(db, limit=6, entity_ids=entity_ids),
            "selected_period": date.today().strftime("%Y-%m"),
            "entities": entities,
            "selected_entity": entity_id_parsed,
        },
    )


@router.get("/expenses-by-category")
def expenses_by_category(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    period: str = Query(default=""),
    entity_id: str = Query(default=""),
):
    memberships = entity_membership_crud.get_by_user(db, current_user.id)
    entity_ids = [m.entity_id for m in memberships]
    entities = [m.entity for m in memberships]
    entity_id_parsed = uuid.UUID(entity_id) if entity_id else None

    if entity_id_parsed and entity_id_parsed in entity_ids:
        entity_ids = [entity_id_parsed]

    if period:
        year, month = period.split("-")
        year = int(year)
        month = int(month)
    else:
        year = None
        month = None

    by_category = get_expenses_by_category(
        db, year=year, month=month, limit=6, entity_ids=entity_ids
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard/_category_chart.html",
        context={
            "by_category": by_category,
            "entities": entities,
            "selected_entity": entity_id_parsed,
        },
    )
