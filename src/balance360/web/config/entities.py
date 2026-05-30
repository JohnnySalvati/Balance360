import uuid
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.crud import entity as entity_crud
from balance360.schemas.entity import EntityCreate, EntityUpdate
from balance360.enums import CondicionIva

router = APIRouter(prefix="/entities")
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

@router.get("/", response_class=HTMLResponse)
def entities_page(request: Request, db: Session = Depends(get_db)):
    entities = entity_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="config/entities/list.html",
        context={"entities": entities}
    )

@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')

@router.get("/rows")
def entities_rows(request: Request, db: Session = Depends(get_db)):
    entities = entity_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="config/entities/_rows.html",
        context={"entities": entities}
    )

@router.get("/new-form")
def new_entity_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="config/entities/_form_modal.html",
        context={"condicion_iva": CondicionIva}
    )

@router.post("/", response_class=HTMLResponse)
def create_entity(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    tax_id: str = Form(default=""),
    condicion_iva: str = Form(...),
):
    entity_crud.create(db, EntityCreate(
        name=name,
        tax_id=tax_id or None,
        condicion_iva=CondicionIva[condicion_iva],
    ))
    response = HTMLResponse('<div id="modal"></div>')
    response.headers['HX-Trigger'] = "refreshRows"
    return response

@router.get("/{entity_id}/edit-form", response_class=HTMLResponse)
def entity_edit_form(
    request: Request,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        request=request,
        name="config/entities/_form_modal.html",
        context={
            "entity": entity_crud.get_by_id(db, entity_id),
            "condicion_iva": CondicionIva,
        }
    )

@router.patch("/{entity_id}", response_class=HTMLResponse)
def update_entity(
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    name: str = Form(...),
    tax_id: str = Form(default=""),
    condicion_iva: str = Form(...),
):
    entity = entity_crud.get_by_id(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity_crud.update(db, entity, EntityUpdate(
        name=name,
        tax_id=tax_id or None,
        condicion_iva=CondicionIva[condicion_iva],
    ))
    response = HTMLResponse('<div id="modal"></div>')
    response.headers['HX-Trigger'] = "refreshRows"
    return response

@router.delete("/{entity_id}", response_class=HTMLResponse)
def delete_entity(entity_id: uuid.UUID, db: Session = Depends(get_db)):
    entity = entity_crud.get_by_id(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    if entity.transactions:
        return HTMLResponse(
            '<tr><td colspan="4" class="px-4 py-2 text-red-600 text-sm">'
            f'No se puede eliminar "{entity.name}": tiene transacciones asociadas.'
            '</td></tr>'
        )
    entity_crud.delete(db, entity)
    return HTMLResponse("")
