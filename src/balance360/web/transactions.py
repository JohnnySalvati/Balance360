import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from balance360.crud import account as account_crud
from balance360.crud import category as category_crud
from balance360.crud import contact as contact_crud
from balance360.crud import entity as entity_crud
from balance360.crud import import_rule as import_rule_crud
from balance360.crud import transaction as transaction_crud
from balance360.dependencies import Period, get_db, get_period
from balance360.enums import ClassificationStatus, TransactionType
from balance360.schemas.transaction import TransactionCreate, TransactionUpdate
from balance360.services import transaction as transaction_service
from balance360.services.import_rule import (
    Classification,
    RuleConflictError,
    find_best_rule,
    resolve_rule_for_classification,
)
from balance360.web.templating import templates

router = APIRouter()

PAGE_SIZE = 50


@dataclass
class TransactionFilters:
    """Los filtros propios de esta pantalla, tal cual llegan del form (strings crudos).

    Se guardan sin parsear por la misma razón que `Period` guarda year y month asi:
    el template los vuelve a pintar en los `<select>` comparando strings. La
    conversión a los tipos que espera el crud vive en `as_crud_kwargs`, un solo
    lugar para los dos que la necesitan (la grilla y "reaplicar reglas").

    El período NO está acá: viene aparte en un `Period`, igual que en los reportes.
    """

    transaction_type: str = ""
    account_id: str = ""
    classification_status: str = ""
    description: str = ""
    entity_id: str = ""
    category_id: str = ""

    def as_crud_kwargs(self) -> dict[str, Any]:
        return {
            "transaction_type": (
                TransactionType(self.transaction_type) if self.transaction_type else None
            ),
            "account_id": UUID(self.account_id) if self.account_id else None,
            "classification_status": (
                ClassificationStatus(self.classification_status)
                if self.classification_status
                else None
            ),
            "description": self.description,
            "entity_id": UUID(self.entity_id) if self.entity_id else None,
            "category_id": UUID(self.category_id) if self.category_id else None,
        }


def get_transaction_filters(
    transaction_type: str = Query(default=""),
    account_id: str = Query(default=""),
    classification_status: str = Query(default=""),
    description: str = Query(default=""),
    entity_id: str = Query(default=""),
    category_id: str = Query(default=""),
) -> TransactionFilters:
    return TransactionFilters(
        transaction_type=transaction_type,
        account_id=account_id,
        classification_status=classification_status,
        description=description,
        entity_id=entity_id,
        category_id=category_id,
    )


def rows_context(
    db: Session, period: Period, filters: TransactionFilters, page: int
) -> dict[str, Any]:
    """Contexto de `transactions/rows.html`.

    El período entra como date_from/date_to del crud: `Period` ya resolvió la
    prioridad entre "desde/hasta" y el par año/mes.

    La entidad vacía significa *sin filtrar*, no "las entidades del usuario" como
    en los reportes: una transacción recién importada tiene `entity_id` en NULL y
    clasificarla es justamente para lo que existe esta pantalla. Un `IN (...)`
    sobre una columna NULL da NULL —no False— y las esconderia a todas.
    """
    query = filters.as_crud_kwargs() | {"date_from": period.start, "date_to": period.end}
    filtered_count = transaction_crud.count_all(db, **query)

    return {
        "transactions": transaction_crud.get_all(
            db, **query, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE
        ),
        "total_count": transaction_crud.count_all(db),
        "filtered_count": filtered_count,
        "page": page,
        "total_pages": (filtered_count + PAGE_SIZE - 1) // PAGE_SIZE,
        "entities": entity_crud.get_all(db),
        "contacts": contact_crud.get_all(db),
        "categories": category_crud.get_all(db),
        "accounts": account_crud.get_all(db),
    }


@router.get("/transactions")
def transaction_list(
    request: Request,
    db: Session = Depends(get_db),
    period: Period = Depends(get_period),
    filters: TransactionFilters = Depends(get_transaction_filters),
):
    return templates.TemplateResponse(
        request=request,
        name="transactions/list.html",
        context={
            "period": period,
            "filters": filters,
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "accounts": account_crud.get_all(db),
        },
    )


@router.get("/transactions/rows")
def transaction_rows(
    request: Request,
    db: Session = Depends(get_db),
    period: Period = Depends(get_period),
    filters: TransactionFilters = Depends(get_transaction_filters),
    page: int = Query(default=1),
):
    return templates.TemplateResponse(
        request=request,
        name="transactions/rows.html",
        context=rows_context(db, period, filters, page),
    )


@router.get("/transactions/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')


@router.get("/transactions/new-form")
def new_transaction_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="transactions/_form_modal.html",
        context={
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "accounts": account_crud.get_all(db),
        },
    )


@router.post("/transactions/create")
def create_transaction(
    request: Request,
    db: Session = Depends(get_db),
    transaction_date: str = Form(...),
    description: str = Form(...),
    amount: str = Form(...),
    transaction_type: str = Form(...),
    account_id: str = Form(...),
    entity_id: str = Form(default=""),
    contact_id: str = Form(default=""),
    category_id: str = Form(default=""),
    is_transfer: bool = Form(default=False),
):

    data = TransactionCreate(
        date=date.fromisoformat(transaction_date),
        description=description,
        amount=Decimal(amount),
        type=TransactionType(transaction_type),
        account_id=UUID(account_id),
        entity_id=UUID(entity_id) if entity_id else None,
        contact_id=UUID(contact_id) if contact_id else None,
        category_id=UUID(category_id) if category_id else None,
        is_manual=True,
        is_transfer=is_transfer,
    )
    transaction_crud.create(db, data)

    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.patch("/transactions/{transaction_id}/classify")
def classify_transaction(
    request: Request,
    transaction_id: UUID,
    db: Session = Depends(get_db),
    entity_id: UUID | None = Form(default=None),
    contact_id: UUID | None = Form(default=None),
    category_id: UUID | None = Form(default=None),
    create_rule: bool = Form(default=False),
    is_transfer: bool = Form(default=False),
    force: bool = Form(default=False),
):
    transaction = transaction_crud.get_by_id(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    entities = entity_crud.get_all(db)
    contacts = contact_crud.get_all(db)
    categories = category_crud.get_all(db)

    def row_response(extra_trigger: dict | None = None):
        resp = templates.TemplateResponse(
            request=request,
            name="transactions/row.html",
            context={
                "t": transaction,
                "entities": entities,
                "contacts": contacts,
                "categories": categories,
            },
        )

        resp.headers["HX-Trigger"] = "refreshChart"

        if extra_trigger:
            resp.headers["HX-Trigger"] = json.dumps(extra_trigger)
            resp.headers["HX-Reswap"] = "none"
        return resp

    rule = None
    if create_rule:
        try:
            classification = Classification(
                entity_id=entity_id,
                contact_id=contact_id,
                category_id=category_id,
                is_transfer=is_transfer,
                account_id=None,
            )
            rule = resolve_rule_for_classification(
                db=db,
                description=transaction.description,
                transaction_type=transaction.type,
                classification=classification,
                force=force,
            )
        except RuleConflictError as e:
            return row_response(
                {
                    "showRuleConflict": {
                        "row_id": f"row-{transaction_id}",
                        "pattern": e.pattern,
                        "count": e.count,
                    }
                }
            )
    data = {
        "entity_id": entity_id,
        "contact_id": contact_id,
        "category_id": category_id,
        "is_manual": True,
        "is_transfer": is_transfer,
        "applied_rule_id": rule.id if rule else None,
    }

    transaction = transaction_crud.update(
        db=db, transaction=transaction, data=TransactionUpdate(**data)
    )

    return row_response()


@router.post("/transactions/apply-rules")
def apply_rules(
    request: Request,
    db: Session = Depends(get_db),
    year: str = Form(default=""),
    month: str = Form(default=""),
    date_from: str = Form(default=""),
    date_to: str = Form(default=""),
    transaction_type: str = Form(default=""),
    account_id: str = Form(default=""),
    classification_status: str = Form(default=""),
    description: str = Form(default=""),
    entity_id: str = Form(default=""),
    category_id: str = Form(default=""),
    page: int = Query(default=1),
):
    all_transactions = [t for t in transaction_crud.get_all(db) if not t.is_manual]
    import_rules = import_rule_crud.get_all(db)
    for transaction in all_transactions:
        import_rule = find_best_rule(transaction.description, transaction.type, import_rules)
        if import_rule:
            transaction_data = TransactionUpdate(
                entity_id=import_rule.entity_id,
                contact_id=import_rule.contact_id,
                category_id=import_rule.category_id,
                is_transfer=import_rule.is_transfer,
                applied_rule_id=import_rule.id,
            )
            for field, value in transaction_data.model_dump(exclude_unset=True).items():
                setattr(transaction, field, value)
    db.flush()

    # `get_period` y `get_transaction_filters` leen de la query string, y acá los
    # filtros llegan en el body del POST: se las llama como funciones comunes con
    # los valores del form. Mismo recurso que usa `get_evolution_period`.
    period = get_period(year=year, month=month, date_from=date_from, date_to=date_to)
    filters = TransactionFilters(
        transaction_type=transaction_type,
        account_id=account_id,
        classification_status=classification_status,
        description=description,
        entity_id=entity_id,
        category_id=category_id,
    )

    response = templates.TemplateResponse(
        request=request,
        name="transactions/rows.html",
        context=rows_context(db, period, filters, page),
    )
    response.headers["HX-Trigger"] = "refreshChart"
    return response


@router.get("/transactions/status-chart")
def status_chart(request: Request, db: Session = Depends(get_db)):
    all_transactions = transaction_crud.get_all(db)
    counts = {s: 0 for s in ClassificationStatus}
    for t in all_transactions:
        counts[t.classification_status] += 1
    return templates.TemplateResponse(
        request=request,
        name="transactions/_status_chart.html",
        context={"counts": counts, "ClassificationStatus": ClassificationStatus},
    )


@router.get("/transactions/{transaction_id}/edit-form")
def transaction_edit_form(request: Request, transaction_id: UUID, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="transactions/_form_modal.html",
        context={
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "accounts": account_crud.get_all(db),
            "transaction": transaction_crud.get_by_id(db, transaction_id),
        },
    )


@router.delete("/transactions/{transaction_id}")
def transaction_delete(transaction_id: UUID, db: Session = Depends(get_db)):
    transaction = transaction_crud.get_by_id(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    transaction_service.delete(db, transaction)
    return HTMLResponse("")


@router.patch("/transactions/{transaction_id}/update")
def transaction_update(
    request: Request,
    transaction_id: UUID,
    db: Session = Depends(get_db),
    transaction_date: str = Form(...),
    description: str = Form(...),
    amount: str = Form(...),
    transaction_type: str = Form(...),
    account_id: str = Form(...),
    entity_id: str = Form(default=""),
    contact_id: str = Form(default=""),
    category_id: str = Form(default=""),
    is_manual: bool = Form(default=True),
    is_transfer: bool = Form(default=False),
    applied_rule_id: str = Form(default=""),
):

    date_parsed = date.fromisoformat(transaction_date) if transaction_date else None
    amount_parsed = Decimal(amount)
    transaction_type_parsed = TransactionType(transaction_type)
    account_id_parsed = UUID(account_id)
    entity_id_parsed = UUID(entity_id) if entity_id else None
    contact_id_parsed = UUID(contact_id) if contact_id else None
    category_id_parsed = UUID(category_id) if category_id else None
    applied_rule_id_parsed = UUID(applied_rule_id) if applied_rule_id else None

    transaction = transaction_crud.get_by_id(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    data = TransactionUpdate(
        date=date_parsed,
        description=description,
        amount=amount_parsed,
        type=transaction_type_parsed,
        account_id=account_id_parsed,
        entity_id=entity_id_parsed,
        contact_id=contact_id_parsed,
        category_id=category_id_parsed,
        is_manual=is_manual,
        is_transfer=is_transfer,
        applied_rule_id=applied_rule_id_parsed,
    )

    transaction_crud.update(db=db, transaction=transaction, data=data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response
