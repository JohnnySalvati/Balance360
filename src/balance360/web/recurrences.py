"""Pantalla de Previsiones: el ABM de los planes.

Existe por una razón concreta y no por prolijidad: una recurrencia creada desde una
transacción que después se borró quedaría sin ninguna pantalla que la muestre, generando
fantasmas para siempre sin forma de apagarla.

Cuelga de `/recurrences/` y se llega desde el botón de Transacciones, igual que
`/import-rules/`: son las dos pantallas satélite de la grilla.
"""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from balance360.crud import account as account_crud
from balance360.crud import category as category_crud
from balance360.crud import contact as contact_crud
from balance360.crud import entity as entity_crud
from balance360.crud import recurrence as recurrence_crud
from balance360.dependencies import get_db
from balance360.enums import IntervalUnit, TransactionType
from balance360.schemas.recurrence import RecurrenceCreate, RecurrenceUpdate
from balance360.web.responses import format_validation_error, toast_error
from balance360.web.templating import templates

router = APIRouter(prefix="/recurrences")


def _catalogs(db: Session) -> dict:
    return {
        "entities": entity_crud.get_all(db),
        "contacts": contact_crud.get_all(db),
        "categories": category_crud.get_all(db),
        "accounts": account_crud.get_all(db),
        "interval_units": IntervalUnit,
        "transaction_types": TransactionType,
    }


def _get_or_404(db: Session, recurrence_id: uuid.UUID):
    recurrence = recurrence_crud.get_by_id(db, recurrence_id)
    if not recurrence:
        raise HTTPException(status_code=404, detail="Recurrence not found")
    return recurrence


@router.get("/", response_class=HTMLResponse)
def recurrences_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="recurrences/list.html",
        context={"recurrences": recurrence_crud.get_all(db)} | _catalogs(db),
    )


@router.get("/rows")
def recurrences_rows(request: Request, db: Session = Depends(get_db), description: str = ""):
    return templates.TemplateResponse(
        request=request,
        name="recurrences/_rows.html",
        context={"recurrences": recurrence_crud.get_all(db, description)} | _catalogs(db),
    )


@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')


@router.get("/new-form")
def new_recurrence_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="recurrences/_form_modal.html",
        context=_catalogs(db),
    )


@router.get("/{recurrence_id}/edit-form")
def recurrence_edit_form(request: Request, recurrence_id: uuid.UUID, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="recurrences/_form_modal.html",
        context={"recurrence": _get_or_404(db, recurrence_id)} | _catalogs(db),
    )


def _form_fields(
    description: str,
    amount: str,
    transaction_type: str,
    account_id: str,
    entity_id: str,
    contact_id: str,
    category_id: str,
    is_transfer: bool,
    interval_unit: str,
    interval_count: str,
    starts_on: str,
    ends_on: str,
) -> dict:
    return {
        "description": description,
        "amount": Decimal(amount),
        "type": TransactionType(transaction_type),
        "account_id": uuid.UUID(account_id),
        "entity_id": uuid.UUID(entity_id) if entity_id else None,
        "contact_id": uuid.UUID(contact_id) if contact_id else None,
        "category_id": uuid.UUID(category_id) if category_id else None,
        "is_transfer": is_transfer,
        "interval_unit": IntervalUnit(interval_unit),
        "interval_count": int(interval_count) if interval_count else 1,
        "starts_on": date.fromisoformat(starts_on),
        "ends_on": date.fromisoformat(ends_on) if ends_on else None,
    }


@router.post("/create")
def create_recurrence(
    db: Session = Depends(get_db),
    description: str = Form(...),
    amount: str = Form(...),
    transaction_type: str = Form(...),
    account_id: str = Form(...),
    entity_id: str = Form(default=""),
    contact_id: str = Form(default=""),
    category_id: str = Form(default=""),
    is_transfer: bool = Form(default=False),
    interval_unit: str = Form(...),
    interval_count: str = Form(default="1"),
    starts_on: str = Form(...),
    ends_on: str = Form(default=""),
):
    fields = _form_fields(
        description,
        amount,
        transaction_type,
        account_id,
        entity_id,
        contact_id,
        category_id,
        is_transfer,
        interval_unit,
        interval_count,
        starts_on,
        ends_on,
    )
    try:
        recurrence_crud.create(db, RecurrenceCreate(**fields))
    except ValidationError as e:
        return toast_error(format_validation_error(e))

    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.patch("/{recurrence_id}")
def update_recurrence(
    recurrence_id: uuid.UUID,
    db: Session = Depends(get_db),
    description: str = Form(...),
    amount: str = Form(...),
    transaction_type: str = Form(...),
    account_id: str = Form(...),
    entity_id: str = Form(default=""),
    contact_id: str = Form(default=""),
    category_id: str = Form(default=""),
    is_transfer: bool = Form(default=False),
    interval_unit: str = Form(...),
    interval_count: str = Form(default="1"),
    starts_on: str = Form(...),
    ends_on: str = Form(default=""),
):
    recurrence = _get_or_404(db, recurrence_id)
    fields = _form_fields(
        description,
        amount,
        transaction_type,
        account_id,
        entity_id,
        contact_id,
        category_id,
        is_transfer,
        interval_unit,
        interval_count,
        starts_on,
        ends_on,
    )
    try:
        recurrence_crud.update(db, recurrence, RecurrenceUpdate(**fields))
    except ValidationError as e:
        db.rollback()
        return toast_error(format_validation_error(e))

    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.post("/{recurrence_id}/toggle")
def toggle_recurrence(request: Request, recurrence_id: uuid.UUID, db: Session = Depends(get_db)):
    """Pausar o reanudar. Es la operación que reemplaza a borrar en el uso diario.

    Una serie que terminó no se borra: se apaga, y las transacciones reales que la tuvieron
    conservan a qué plan pertenecieron. Borrar dispara el `SET NULL` y eso se pierde.
    """
    recurrence = _get_or_404(db, recurrence_id)
    recurrence_crud.update(db, recurrence, RecurrenceUpdate(is_active=not recurrence.is_active))
    return templates.TemplateResponse(
        request=request,
        name="recurrences/_row.html",
        context={"r": recurrence} | _catalogs(db),
    )


@router.delete("/{recurrence_id}")
def delete_recurrence(recurrence_id: uuid.UUID, db: Session = Depends(get_db)):
    recurrence_crud.delete(db, _get_or_404(db, recurrence_id))
    return HTMLResponse("")
