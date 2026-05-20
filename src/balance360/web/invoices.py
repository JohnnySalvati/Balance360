import uuid
import datetime
from decimal import Decimal
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.crud import invoice as invoice_crud
from balance360.crud import entity as entity_crud
from balance360.crud import contact as contact_crud
from balance360.crud import category as category_crud
from balance360.crud import account as account_crud
from balance360.crud import product as product_crud
from balance360.crud import invoice_line as invoice_line_crud
from balance360.schemas.invoice import InvoiceCreate, InvoiceUpdate
from balance360.schemas.invoice_line import InvoiceLineCreate
from balance360.services import invoice as invoice_service
from balance360.enums import InvoiceType, VoucherType

router = APIRouter(prefix="/invoices")
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

templates.env.filters["currency"] = lambda v: f"${v:,.2f}"

@router.get("/", response_class=HTMLResponse)
def invoice_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="invoices/list.html",
        context={
            "invoices": invoice_crud.get_all(db)
        }
    )

@router.get("/new")
def new_invoice_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="invoices/new_form.html",
        context={
            "invoice_type": InvoiceType,
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "voucher_type": VoucherType
        }
    )    

@router.get("/{invoice_id}")
def invoice_edit_form(request: Request, invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice =invoice_crud.get_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return templates.TemplateResponse(
        request=request,
        name="invoices/detail.html",
        context={
            "invoice": invoice,
            "accounts": account_crud.get_all(db)
        }
    )

@router.post("/", response_class=HTMLResponse)
def create_invoice(
    db: Session = Depends(get_db),
    invoice_type: str = Form(...),
    entity_id: str = Form(...),
    contact_id: str = Form(...),
    category_id: str|None = Form(default=""),
    date: str = Form(...),
    formal: bool|None = Form(default=False),
    tax_only: bool|None = Form(default=False),
    voucher_type: str|None = Form(default=""),
    pos: str|None = Form(default=""),
    number: str|None = Form(default=""),
):
    data = InvoiceCreate(
        invoice_type=InvoiceType(invoice_type),
        entity_id=uuid.UUID(entity_id),
        contact_id=uuid.UUID(contact_id),
        category_id=uuid.UUID(category_id) if category_id else None,
        date=datetime.date.fromisoformat(date),
        formal=formal if formal else False,
        tax_only=tax_only if tax_only else False,
        voucher_type=VoucherType(voucher_type) if voucher_type else None,
        pos=int(pos) if pos else None,
        number=int(number) if number else None,
    )
    invoice = invoice_crud.create(db, data)
    return RedirectResponse(url=f"/invoices/{invoice.id}", status_code=303)

@router.patch("/{invoice_id}", response_class=HTMLResponse)
def update_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    invoice_type: str|None = Form(default=""),
    entity_id: str|None = Form(default=""),
    contact_id: str|None = Form(default=""),
    category_id: str|None = Form(default=""),
    date: str|None = Form(default=""),
    formal: bool|None = Form(default=None),
    tax_only: bool|None = Form(default=None),
    voucher_type: str|None = Form(default=""),
    pos: str|None = Form(default=""),
    number: str|None = Form(default=""),
):
    invoice =invoice_crud.get_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    data = InvoiceUpdate(
        invoice_type=InvoiceType(invoice_type) if invoice_type else None,
        entity_id=uuid.UUID(entity_id) if entity_id else None,
        contact_id=uuid.UUID(contact_id) if contact_id else None,
        category_id=uuid.UUID(category_id) if category_id else None,
        date=datetime.date.fromisoformat(date) if date else None,
        formal=bool(formal),
        tax_only=bool(tax_only),
        voucher_type=VoucherType(voucher_type) if voucher_type else None,
        pos=int(pos) if pos else None,
        number=int(number) if number else None,
    )   
    invoice = invoice_crud.update(db, data, invoice)
    return RedirectResponse(url=f"/invoices/{invoice.id}", status_code=303)

@router.get("/{invoice_id}/lines/new-form", response_class=HTMLResponse)
def new_line_form(
    invoice_id: uuid.UUID,
    request: Request, 
    db: Session = Depends(get_db),
    ):
    invoice = invoice_crud.get_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return templates.TemplateResponse(
        request=request,
        name="invoices/new_line_form.html",
        context={
            "invoice": invoice,
            "products": product_crud.get_all(db),
        }
    )

@router.delete("/{invoice_id}/lines/{invoice_line_id}", response_class=HTMLResponse)
def delete_invoice_line(
    invoice_id: uuid.UUID,
    invoice_line_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    invoice = invoice_crud.get_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice_line = invoice_line_crud.get_by_id(db, invoice_line_id)
    if not invoice_line:
        raise HTTPException(status_code=404, detail="Invoice line not found")
    invoice_line_crud.delete(db, invoice_line)
    return HTMLResponse("")

@router.post("/{invoice_id}/confirm", response_class=HTMLResponse)
def confirm_invoice(
    invoice_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    account_id: str|None = Form(default=""),
    payment_date: str|None = Form(default="")
):
    account_id_parsed = uuid.UUID(account_id) if account_id else None
    payment_date_parsed = datetime.date.fromisoformat(payment_date) if payment_date else None

    invoice = invoice_crud.get_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    account = account_crud.get_by_id(db, account_id_parsed) if account_id_parsed else None

    try:
        invoice_service.confirm_invoice(db, invoice, account, payment_date_parsed)
    except invoice_service.InvoiceConfirmError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)

@router.post("/{invoice_id}/lines", response_class=HTMLResponse)
def create_invoice_line(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    product_id: str|None = Form(default=""),
    description: str|None = Form(default=""),
    quantity: str = Form(...),
    unit_price: str = Form(...),
):
    product_id_parsed = uuid.UUID(product_id) if product_id else None
    quantity_parsed = int(quantity)
    unit_price_parsed = Decimal(unit_price)

    invoice = invoice_crud.get_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    data = InvoiceLineCreate(
        invoice_id=invoice_id,
        product_id=product_id_parsed,
        description=description or None,
        quantity=quantity_parsed,
        unit_price=unit_price_parsed
    )

    invoice_line_crud.create(db, data)
    return RedirectResponse(url=f"/invoices/{invoice.id}", status_code=303)

@router.get("/{invoice_id}/lines/close-form", response_class=HTMLResponse)
def close_line_form(invoice_id: uuid.UUID):
    return HTMLResponse("")


@router.get("/{invoice_id}/edit")
def edit_invoice_form(request: Request, invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = invoice_crud.get_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return templates.TemplateResponse(
        request=request,
        name="invoices/edit_form.html",
        context={
            "invoice": invoice,
            "invoice_type": InvoiceType,
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "voucher_type": VoucherType,
        }
    )