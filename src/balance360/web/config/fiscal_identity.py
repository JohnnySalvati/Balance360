import uuid
from decimal import Decimal
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from balance360.models.fiscal_identity import FiscalIdentity
from balance360.models.entity import Entity
from balance360.crud import fiscal_identity as fiscal_identity_crud
from balance360.crud import entity as entity_crud
from balance360.dependencies import get_db
from balance360.schemas.fiscal_identity import FiscalIdentityCreate, FiscalIdentityUpdate
from balance360.web.templating import templates
from balance360.enums import CondicionIva

router = APIRouter(prefix="/entities")


def get_fiscal_identity_or_404(fiscal_identity_id: uuid.UUID, db: Session = Depends(get_db)):
    fiscal_identity = fiscal_identity_crud.get_by_id(db, fiscal_identity_id)
    if not fiscal_identity:
        raise HTTPException(status_code=404, detail="Fiscal identity not found")
    return fiscal_identity


def get_entity_or_404(entity_id: uuid.UUID, db: Session = Depends(get_db)):
    entity = entity_crud.get_by_id(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/{entity_id}/fiscal_identities", response_class=HTMLResponse, name="fiscal_identities")
def fiscal_identity_page(
    request: Request,
    db: Session = Depends(get_db),
    entity: Entity = Depends(get_entity_or_404),
):
    return templates.TemplateResponse(
        request=request,
        name="fiscal_identities/list.html",
        context={
            "fiscal_identities": fiscal_identity_crud.get_for_entity(db, entity_id=entity.id),
            "entity": entity,
            "condicion_iva": CondicionIva
        },
    )


@router.get("/{entity_id}/fiscal_identities/rows")
def fiscal_identity_rows(
    request: Request,
    db: Session = Depends(get_db),
    entity: Entity = Depends(get_entity_or_404),
):
    return templates.TemplateResponse(
        request=request,
        name="fiscal_identities/_rows.html",
        context={
            "fiscal_identities": fiscal_identity_crud.get_for_entity(db, entity_id=entity.id),
            "entity": entity,
            "condicion_iva": CondicionIva
        },
    )


@router.get("/{entity_id}/fiscal_identities/new-form")
def new_fiscal_identity_form(
    request: Request,
    db: Session = Depends(get_db),
    entity: Entity = Depends(get_entity_or_404)
):
    return templates.TemplateResponse(
        request=request,
        name="fiscal_identities/_form_modal.html",
        context={
            "entity": entity,
            "condicion_iva": CondicionIva
        },
    )


@router.post("/{entity_id}/fiscal_identities", response_class=HTMLResponse)
def create_fiscal_identity(
    db: Session = Depends(get_db),
    entity: Entity = Depends(get_entity_or_404),
    name: str = Form(...),
    tax_id: str = Form(...),
    condicion_iva: str = Form(...),
    iibb_rate: str = Form(...),
    address: str = Form(...),
    iibb: str = Form(...),
    start_date: str = Form(...)
):
    
    fiscal_identity_crud.create(
        db, FiscalIdentityCreate(
            entity_id=entity.id,
            name=name,
            tax_id=tax_id,
            condicion_iva=CondicionIva[condicion_iva],
            iibb_rate=Decimal(iibb_rate),
            address=address,
            iibb=iibb,
            start_date=date.fromisoformat(start_date)
        )
    )
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshFiscalIdentities"
    return response


@router.get("/{entity_id}/fiscal_identities/{fiscal_identity_id}/edit-form", response_class=HTMLResponse)
def entity_edit_form(
    request: Request,
    entity: Entity = Depends(get_entity_or_404),
    fiscal_identity: FiscalIdentity = Depends(get_fiscal_identity_or_404)
):
    return templates.TemplateResponse(
        request=request,
        name="fiscal_identities/_form_modal.html",
        context={
            "entity": entity,
            "fiscal_identity": fiscal_identity,
            "condicion_iva": CondicionIva,
        },
    )


@router.patch("/{entity_id}/fiscal_identities/{fiscal_identity_id}", response_class=HTMLResponse)
def update_fiscal_identity(
    fiscal_identity=Depends(get_fiscal_identity_or_404),
    db: Session = Depends(get_db),
    name: str|None = Form(default=""),
    tax_id: str|None = Form(default=""),
    condicion_iva: str|None = Form(default=""),
    iibb_rate: str|None = Form(default=""),
    address: str|None = Form(default=""),
    iibb: str|None = Form(default=""),
    start_date: str|None = Form(default=""),
):
    data = FiscalIdentityUpdate(
            name=name if name else None,
            tax_id=tax_id if tax_id else None,
            condicion_iva=CondicionIva[condicion_iva] if condicion_iva else None,
            iibb_rate=Decimal(iibb_rate) if iibb_rate else None,
            address=address if address else None,
            iibb=iibb if iibb else None,
            start_date=date.fromisoformat(start_date) if start_date else None
    )
    fiscal_identity_crud.update(db, fiscal_identity, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshFiscalIdentities"
    return response


@router.delete("/{entity_id}/fiscal_identities/{fiscal_identity_id}", response_class=HTMLResponse)
def delete_fiscal_identity(
    fiscal_identity=Depends(get_fiscal_identity_or_404),
    db: Session = Depends(get_db),
):
    fiscal_identity_crud.delete(db, fiscal_identity)
    
    response = HTMLResponse("")
    response.headers["HX-Trigger"] = "refreshFiscalIdentities"
    return response
