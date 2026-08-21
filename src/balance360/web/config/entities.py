import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from balance360.crud import entity as entity_crud
from balance360.crud import entity_membership as entity_membership_crud
from balance360.crud import fiscal_identity as fiscal_identity_crud
from balance360.crud import user as user_crud
from balance360.dependencies import get_db
from balance360.enums import Role
from balance360.models.entity import Entity
from balance360.models.entity_membership import EntityMembership
from balance360.schemas.entity import EntityCreate, EntityUpdate
from balance360.schemas.entity_membership import (
    EntityMembershipCreate,
    EntityMembershipUpdate,
)
from balance360.web.templating import templates

router = APIRouter(prefix="/entities")


@router.get("/", response_class=HTMLResponse)
def entities_page(request: Request, db: Session = Depends(get_db)):
    entities = entity_crud.get_all(db)
    return templates.TemplateResponse(
        request=request, name="config/entities/list.html", context={"entities": entities}
    )


@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')


@router.get("/rows")
def entities_rows(request: Request, search: str = Query(default=""), db: Session = Depends(get_db)):

    entities = entity_crud.get_all(db, search)

    return templates.TemplateResponse(
        request=request, name="config/entities/_rows.html", context={"entities": entities}
    )


@router.get("/new-form")
def new_entity_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="config/entities/_form_modal.html",
        context={"fiscal_identities": fiscal_identity_crud.get_all(db)},
    )


@router.post("/", response_class=HTMLResponse)
def create_entity(
    db: Session = Depends(get_db),
    name: str = Form(...),
    fiscal_identity_ids: list[uuid.UUID] = Form(default=[]),
):
    entity_crud.create(
        db,
        EntityCreate(name=name, fiscal_identity_ids=fiscal_identity_ids),
    )
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.get("/{entity_id}/edit-form", response_class=HTMLResponse)
def entity_edit_form(
    request: Request,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request=request,
        name="config/entities/_form_modal.html",
        context={
            "entity": entity_crud.get_by_id(db, entity_id),
            "fiscal_identities": fiscal_identity_crud.get_all(db),
        },
    )


def get_entity_or_404(entity_id: uuid.UUID, db: Session = Depends(get_db)) -> Entity:
    entity = entity_crud.get_by_id(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.patch("/{entity_id}", response_class=HTMLResponse)
def update_entity(
    entity: Entity = Depends(get_entity_or_404),
    db: Session = Depends(get_db),
    name: str = Form(...),
    fiscal_identity_ids: list[uuid.UUID] = Form(default=[]),
):
    entity_crud.update(
        db,
        entity,
        EntityUpdate(name=name, fiscal_identity_ids=fiscal_identity_ids),
    )
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.delete("/{entity_id}", response_class=HTMLResponse)
def delete_entity(entity: Entity = Depends(get_entity_or_404), db: Session = Depends(get_db)):
    if entity.transactions:
        return HTMLResponse(
            '<tr><td colspan="4" class="px-4 py-2 text-red-600 text-sm">'
            f'No se puede eliminar "{entity.name}": tiene transacciones asociadas.'
            "</td></tr>"
        )
    entity_crud.delete(db, entity)
    return HTMLResponse("")


@router.get("/{entity_id}/memberships", response_class=HTMLResponse)
def entity_membership_list(
    request: Request, entity: Entity = Depends(get_entity_or_404), db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        request=request,
        name="config/entities/_membership_panel.html",
        context={
            "entity": entity,
            "entity_memberships": entity_membership_crud.get_by_entity(db, entity.id),
            "users": user_crud.get_all(db),
            "roles": Role,
        },
    )


@router.post("/{entity_id}/memberships", response_class=HTMLResponse)
def create_entity_membership(
    request: Request,
    db: Session = Depends(get_db),
    entity: Entity = Depends(get_entity_or_404),
    user_id: str = Form(...),
    role: str = Form(...),
    share: str | None = Form(default=""),
):
    data = EntityMembershipCreate(
        entity_id=entity.id,
        user_id=uuid.UUID(user_id),
        role=Role(role),
        share=Decimal(share) if share else None,
    )
    entity_membership_crud.create(db, data)
    return templates.TemplateResponse(
        request=request,
        name="config/entities/_membership_panel.html",
        context={
            "entity": entity,
            "entity_memberships": entity_membership_crud.get_by_entity(db, entity.id),
            "users": user_crud.get_all(db),
            "roles": Role,
        },
    )


def get_entity_membership_or_404(
    membership_id: uuid.UUID, db: Session = Depends(get_db)
) -> EntityMembership:
    entity_membership = entity_membership_crud.get_by_id(db, membership_id)
    if not entity_membership:
        raise HTTPException(status_code=404, detail="Entity membership not found")
    return entity_membership


@router.patch("/{entity_id}/memberships/{membership_id}", response_class=HTMLResponse)
def update_entity_membership(
    entity_membership: EntityMembership = Depends(get_entity_membership_or_404),
    db: Session = Depends(get_db),
    role: str | None = Form(default=""),
    share: str | None = Form(default=""),
):
    data = EntityMembershipUpdate(
        role=Role(role) if role else None, share=Decimal(share) if share else None
    )
    entity_membership_crud.update(db, data, entity_membership)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.delete("/{entity_id}/memberships/{membership_id}")
def delete_entity_membership(
    entity_membership: EntityMembership = Depends(get_entity_membership_or_404),
    db: Session = Depends(get_db),
):
    entity_membership_crud.delete(db, entity_membership)
    return HTMLResponse("")
