import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from balance360.crud import contact as contact_crud
from balance360.dependencies import get_db
from balance360.enums import CondicionIva, ContactType, DocType
from balance360.schemas.contact import ContactCreate, ContactUpdate
from balance360.services import contact as contact_service
from balance360.services import padron as padron_service
from balance360.web.templating import templates

router = APIRouter(prefix="/contacts")


@router.get("/", response_class=HTMLResponse)
def contacts_page(request: Request, db: Session = Depends(get_db)):
    contacts = contact_crud.get_all(db)
    return templates.TemplateResponse(
        request=request, name="config/contacts/list.html", context={"contacts": contacts}
    )


@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')


@router.get("/rows")
def contacts_rows(request: Request, search: str = Query(default=""), db: Session = Depends(get_db)):
    contacts = contact_crud.get_all(db, search)

    return templates.TemplateResponse(
        request=request, name="config/contacts/_rows.html", context={"contacts": contacts}
    )


def _form_context(contact=None):
    return {
        "contact": contact,
        "contact_type": ContactType,
        "condicion_iva": CondicionIva,
        "doc_type": DocType,
    }


@router.get("/padron", response_class=HTMLResponse)
def contact_from_padron(request: Request, tax_id: str = Query(default="")):
    """Completa nombre, condicion IVA y domicilio con lo que ARCA tiene del CUIT.

    No toca la base: devuelve los controles ya cargados para que el alta siga
    siendo un solo submit y se pueda corregir lo que traiga el padron.
    """
    taxpayer = padron_service.get_taxpayer(tax_id)

    return templates.TemplateResponse(
        request=request,
        name="config/contacts/_padron_result.html",
        context={"taxpayer": taxpayer, "condicion_iva": CondicionIva},
    )


@router.get("/new-form")
def new_contact_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request, name="config/contacts/_form_modal.html", context=_form_context()
    )


@router.post("/", response_class=HTMLResponse)
def create_contact(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    trade_name: str | None = Form(default=""),
    tax_id: str = Form(default=""),
    contact_type: str = Form(...),
    condicion_iva: str = Form(...),
    doc_type: str = Form(...),
    email: str | None = Form(default=""),
    address: str | None = Form(default=""),
):
    contact_service.create(
        db,
        ContactCreate(
            name=name,
            trade_name=trade_name or None,
            tax_id=tax_id or None,
            contact_type=ContactType(contact_type),
            condicion_iva=CondicionIva[condicion_iva],
            doc_type=DocType[doc_type],
            email=email or None,
            address=address or None,
        ),
    )
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.get("/{contact_id}/edit-form", response_class=HTMLResponse)
def contact_edit_form(request: Request, contact_id: uuid.UUID, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="config/contacts/_form_modal.html",
        context=_form_context(contact_crud.get_by_id(db, contact_id)),
    )


@router.patch("/{contact_id}", response_class=HTMLResponse)
def update_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    name: str = Form(...),
    trade_name: str | None = Form(default=""),
    tax_id: str = Form(default=""),
    contact_type: str = Form(...),
    condicion_iva: str = Form(...),
    doc_type: str = Form(...),
    email: str | None = Form(default=""),
    address: str | None = Form(default=""),
):
    contact = contact_crud.get_by_id(db, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact_service.update(
        db,
        contact,
        ContactUpdate(
            name=name,
            trade_name=trade_name or None,
            tax_id=tax_id or None,
            contact_type=ContactType(contact_type),
            condicion_iva=CondicionIva[condicion_iva],
            doc_type=DocType[doc_type],
            email=email or None,
            address=address or None,
        ),
    )
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.delete("/{contact_id}", response_class=HTMLResponse)
def delete_contact(contact_id: uuid.UUID, db: Session = Depends(get_db)):
    contact = contact_crud.get_by_id(db, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if contact.transactions:
        return HTMLResponse(
            '<tr><td colspan="5" class="px-4 py-2 text-red-600 text-sm">'
            f'No se puede eliminar "{contact.name}": tiene transacciones asociadas.'
            "</td></tr>"
        )
    contact_crud.delete(db, contact)
    return HTMLResponse("")
