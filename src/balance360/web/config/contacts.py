import uuid
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from balance360.enums import ContactType
from balance360.dependencies import get_db
from balance360.crud import contact as contact_crud
from balance360.schemas.contact import ContactCreate, ContactUpdate

router = APIRouter(prefix="/contacts")
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

@router.get("/", response_class=HTMLResponse)
def contacts_page(request: Request, db: Session = Depends(get_db)):
    contacts = contact_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="config/contacts/list.html",
        context={"contacts": contacts}
    )

@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')

@router.get("/rows")
def contacts_rows(request: Request, db: Session = Depends(get_db)):
    contacts = contact_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="config/contacts/_rows.html",
        context={"contacts": contacts}
    )

@router.get("/new-form")
def new_contact_form(request: Request, db: Session = Depends(get_db)):
    contacts = contact_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="config/contacts/_form_modal.html",
        context={"contacts": contacts, "contact_type": ContactType}
    )

@router.post("/", response_class=HTMLResponse)
def create_contact(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    tax_id: str = Form(default=""),
    contact_type: str = Form(...)
):
    contact_type_parsed = ContactType(contact_type)
    contact_crud.create(db, ContactCreate(name=name, tax_id=tax_id, contact_type=contact_type_parsed))
    response = HTMLResponse('<div id="modal"></div>')
    response.headers['HX-Trigger'] = "refreshRows"
    return response

@router.get("/{contact_id}/edit-form", response_class=HTMLResponse)
def contact_edit_form(
    request: Request,
    contact_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        request=request,
        name="config/contacts/_form_modal.html",
        context={
            "contact": contact_crud.get_by_id(db, contact_id),
            "contact_type": ContactType
            }
    )

@router.patch("/{contact_id}", response_class=HTMLResponse)
def update_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    name: str = Form(...),
    tax_id: str = Form(default=""),
    contact_type: str = Form(...)
):
    contact_type_parsed = ContactType(contact_type)
    contact = contact_crud.get_by_id(db, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact_crud.update(db, contact, ContactUpdate(name=name, tax_id=tax_id, contact_type=contact_type_parsed))
    response = HTMLResponse('<div id="modal"></div>')
    response.headers['HX-Trigger'] = "refreshRows"
    return response

@router.delete("/{contact_id}", response_class=HTMLResponse)
def delete_contact(contact_id: uuid.UUID, db: Session = Depends(get_db)):
    contact = contact_crud.get_by_id(db, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if contact.transactions:
        return HTMLResponse(
            '<tr><td colspan="4" class="px-4 py-2 text-red-600 text-sm">'
            f'No se puede eliminar "{contact.name}": tiene transacciones asociadas.'
            '</td></tr>'
        )
    contact_crud.delete(db, contact)
    return HTMLResponse("")
