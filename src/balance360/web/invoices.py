import uuid
import datetime
import json
from decimal import Decimal
from pydantic import ValidationError
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, HTTPException, UploadFile, File, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.crud import invoice as invoice_crud
from balance360.crud import entity as entity_crud
from balance360.crud import contact as contact_crud
from balance360.crud import category as category_crud
from balance360.crud import account as account_crud
from balance360.crud import product as product_crud
from balance360.crud import invoice_line as invoice_line_crud
from balance360.crud import invoice_tribute as invoice_tribute_crud
from balance360.crud import serial_number as serial_number_crud
from balance360.schemas.invoice import InvoiceCreate, InvoiceUpdate
from balance360.schemas.invoice_line import InvoiceLineCreate, InvoiceLineUpdate
from balance360.schemas.invoice_tribute import InvoiceTributeCreate
from balance360.schemas.product import ProductCreate
from balance360.services import invoice as invoice_service
from balance360.services import serial_number as serial_number_service
from balance360.services.serial_number import SerialValidationError
from balance360.services import product_match as product_match_service
from balance360.exceptions import InvoiceAuthorizationError, InvoiceConfirmationError, InvoicePaymentError
from balance360.models.invoice import Invoice
from balance360.models.invoice_tribute import InvoiceTribute
from balance360.models.invoice_line import InvoiceLine
from balance360.models.product import Product
from balance360.models.serial_number import SerialNumber
from balance360.enums import InvoiceType, VoucherType, IvaAliquot, TributeType

router = APIRouter(prefix="/invoices")
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

templates.env.filters["currency"] = lambda v: f"${v:,.2f}"


def get_invoice_or_404(invoice_id: uuid.UUID, db: Session = Depends(get_db)) -> Invoice:
    invoice =invoice_crud.get_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/", response_class=HTMLResponse)
def invoice_page(request: Request, db: Session = Depends(get_db), invoice_type: InvoiceType|None = None):
    return templates.TemplateResponse(
        request=request,
        name="invoices/list.html",
        context={
            "invoices": invoice_crud.get_all(db, invoice_type),
            "current_type": invoice_type.value if invoice_type else None,
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
def invoice_edit_form(request: Request, invoice: Invoice = Depends(get_invoice_or_404), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="invoices/detail.html",
        context={
            "invoice": invoice,
            "accounts": account_crud.get_all(db),
            "tribute_types": TributeType,
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
    pdf_lines: str|None = Form(default=""),
):
    try:
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

        if pdf_lines:
            import json
            from balance360.enums import IvaAliquot
            from balance360.services import product_match
            products = product_crud.get_all(db)   # cargar el catálogo una sola vez
            for line in json.loads(pdf_lines):
                iva_rate = Decimal(line["iva_rate"])
                # mapear la tasa al enum
                aliquot = next(
                    (a for a in IvaAliquot if a.rate == iva_rate),
                    IvaAliquot.standard
                )
                # auto-vincular el producto solo si el match es muy fuerte;
                # el resto queda sin producto para revisar en el borrador.
                match = product_match.best_match(line["description"], products)
                product_id = (
                    match.product.id
                    if match and match.score >= product_match.AUTO_ACCEPT_SCORE
                    else None
                )
                invoice_line_crud.create(db, InvoiceLineCreate(
                    invoice_id=invoice.id,
                    product_id=product_id,
                    description=line["description"] or None,
                    quantity=int(Decimal(line["quantity"])),
                    unit_price=Decimal(line["unit_price"]),
                    iva_aliquot=aliquot,
                ))
    except (ValidationError, ValueError) as e:
        return HTMLResponse(f'<p class="text-red-600 text-sm">{e}</p>')
    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/invoices/{invoice.id}"}
    )


@router.patch("/{invoice_id}", response_class=HTMLResponse)
def update_invoice(
    invoice: Invoice = Depends(get_invoice_or_404),
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
    try:   
        invoice = invoice_crud.update(db, data, invoice)
    except ValueError as e:
        return HTMLResponse(f'<p class="text-red-600 text-sm">{e}</p>')
    
    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/invoices/{invoice.id}"}
    )


@router.get("/{invoice_id}/lines/new-form", response_class=HTMLResponse)
def new_line_form(
    request: Request, 
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
    ):
    return templates.TemplateResponse(
        request=request,
        name="invoices/new_line_form.html",
        context={
            "invoice": invoice,
            "products": product_crud.get_all(db),
            "iva_aliquots": IvaAliquot,
        }
    )

def get_invoice_line_or_404(invoice_line_id: uuid.UUID, db: Session = Depends(get_db)) -> InvoiceLine:
    invoice_line = invoice_line_crud.get_by_id(db, invoice_line_id)
    if not invoice_line:
        raise HTTPException(status_code=404, detail="Invoice line not found")
    return invoice_line

@router.delete("/{invoice_id}/lines/{invoice_line_id}", response_class=HTMLResponse)
def delete_invoice_line(
    invoice: Invoice = Depends(get_invoice_or_404),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    db: Session = Depends(get_db)
):
    if invoice_line.invoice.id != invoice.id:
        raise HTTPException(status_code=404, detail="Invoice line mistmach invoice")
    
    invoice_line_crud.delete(db, invoice_line)
    return HTMLResponse("")

@router.post("/{invoice_id}/confirm", response_class=HTMLResponse)
def confirm_invoice(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
):
    try:
        invoice_service.confirm_invoice(db, invoice)
    except (InvoiceConfirmationError, InvoicePaymentError) as e:
        return HTMLResponse(f'<p class="text-red-600 text-sm">{e}</p>')

    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/invoices/{invoice.id}"}
    )

@router.post("/{invoice_id}/pay", response_class=HTMLResponse)
def pay_invoice(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
    account_id: str = Form(...),
    payment_date: str = Form(...),
):

    account = account_crud.get_by_id(db, uuid.UUID(account_id))
    if not account:
        return HTMLResponse('<p class="text-red-600 text-sm">Cuenta no encontrada</p>')

    try:
        invoice_service.register_payment(
            db, invoice, account, datetime.date.fromisoformat(payment_date)
        )
    except InvoicePaymentError as e:
        return HTMLResponse(f'<p class="text-red-600 text-sm">{e}</p>')

    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/invoices/{invoice.id}"}
    )

@router.post("/{invoice_id}/lines", response_class=HTMLResponse)
def create_invoice_line(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
    product_id: str|None = Form(default=""),
    description: str|None = Form(default=""),
    quantity: str = Form(...),
    unit_price: str = Form(...),
    iva_aliquot: str = Form(...),
):
    product_id_parsed = uuid.UUID(product_id) if product_id else None
    quantity_parsed = int(quantity)
    unit_price_parsed = Decimal(unit_price)

    data = InvoiceLineCreate(
        invoice_id=invoice.id,
        product_id=product_id_parsed,
        description=description or None,
        quantity=quantity_parsed,
        unit_price=unit_price_parsed,
        iva_aliquot=IvaAliquot[iva_aliquot],
    )

    invoice_line_crud.create(db, data)
    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/invoices/{invoice.id}"}
    )



@router.post("/{invoice_id}/authorize", response_class=HTMLResponse)
def authorize_invoice(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
):
    try:
        invoice_service.authorize_invoice(db, invoice)
    except InvoiceAuthorizationError as e:
        return HTMLResponse(f'<p class="text-red-600 text-sm">{e}</p>')

    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/invoices/{invoice.id}"}
    )



@router.get("/{invoice_id}/lines/close-form", response_class=HTMLResponse)
def close_line_form(invoice_id: uuid.UUID):
    return HTMLResponse("")



def get_tribute_or_404(tribute_id: uuid.UUID, db: Session = Depends(get_db)) -> InvoiceTribute:
    invoice_tribute = invoice_tribute_crud.get_by_id(db, tribute_id)
    if not invoice_tribute:
        raise HTTPException(status_code=404, detail="Invoice tribute not found")
    return invoice_tribute


@router.get("/{invoice_id}/tributes/new-form", response_class=HTMLResponse)
def new_tribute_form(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
):
    return templates.TemplateResponse(
        request=request,
        name="invoices/new_tribute_form.html",
        context={
            "invoice": invoice,
            "tribute_types": TributeType,
        }
    )


@router.post("/{invoice_id}/tributes", response_class=HTMLResponse)
def create_invoice_tribute(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
    tribute_type: str = Form(...),
    description: str = Form(...),
    base_amount: str = Form(...),
    rate: str = Form(...),
):

    data = InvoiceTributeCreate(
        invoice_id=invoice.id,
        tribute_type=TributeType[tribute_type],
        description=description,
        base_amount=Decimal(base_amount),
        rate=Decimal(rate),
    )
    
    try:
        invoice_tribute_crud.create(db, data)
    except ValidationError as e:
        return HTMLResponse(f'<p class="text-red-600 text-sm">{e}</p>')
    
    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/invoices/{invoice.id}"}
    )


@router.delete("/{invoice_id}/tributes/{tribute_id}", response_class=HTMLResponse)
def delete_invoice_tribute(
    invoice: Invoice = Depends(get_invoice_or_404),
    tribute: InvoiceTribute = Depends(get_tribute_or_404),
    db: Session = Depends(get_db),
):
    if tribute.invoice_id != invoice.id:
        raise HTTPException(status_code=404, detail="Invoice tribute mistmach invoice")
    
    invoice_tribute_crud.delete(db, tribute)
    return HTMLResponse("")


@router.get("/{invoice_id}/tributes/close-form", response_class=HTMLResponse)
def close_tribute_form(invoice_id: uuid.UUID):
    return HTMLResponse("")


@router.get("/{invoice_id}/edit")
def edit_invoice_form(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db)
    ):
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

@router.post("/parse-pdf")
async def parse_pdf(
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    from balance360.services.pdf_invoice import parse_invoice_pdf
    content = await file.read()
    parsed = parse_invoice_pdf(content)
    
    # buscar contacto por CUIT
    contact = None
    if parsed.supplier_cuit:
        contact = contact_crud.get_by_tax_id(db, parsed.supplier_cuit)
    
    return {
        "voucher_type": parsed.voucher_type,
        "pos": parsed.pos,
        "number": parsed.number,
        "date": parsed.date.isoformat() if parsed.date else None,
        "supplier_cuit": parsed.supplier_cuit,
        "supplier_name": parsed.supplier_name,
        "supplier_condicion_iva": parsed.supplier_condicion_iva,
        "cae": parsed.cae,
        "contact_id": str(contact.id) if contact else None,
        "contact_found": contact is not None,
        "lines": [
            {
                "description": l.description,
                "quantity": str(l.quantity),
                "unit_price": str(l.unit_price),
                "iva_rate": str(l.iva_rate),
            }
            for l in parsed.lines
        ],
        "needs_manual_items": parsed.needs_manual_items,
    }

@router.post("/quick-contact")
async def quick_contact(
    db: Session = Depends(get_db),
    name: str = Form(...),
    tax_id: str = Form(...),
    condicion_iva: str = Form(...),
):
    from balance360.schemas.contact import ContactCreate
    from balance360.enums import CondicionIva, ContactType, DocType
    data = ContactCreate(
        name=name,
        tax_id=tax_id,
        contact_type=ContactType.supplier,
        condicion_iva=CondicionIva[condicion_iva],
        doc_type=DocType.CUIT,
    )
    contact = contact_crud.create(db, data)
    return {"id": str(contact.id), "name": contact.name}

@router.delete("/{invoice_id}", response_class=HTMLResponse)
def delete_invoice(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db)
    ):
    invoice_crud.delete(db, invoice)
    return HTMLResponse("")


@router.get("/{invoice_id}/lines/{invoice_line_id}/match-form", response_class= HTMLResponse)
def match_product_suggestions(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    db: Session = Depends(get_db)
): 
    suggestions = product_match_service.suggest(
        invoice_line.description,
        product_crud.get_all(db), 
        limit=5 )
    
    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/match_form.html",
        context={
            "suggestions": suggestions,
            "invoice": invoice,
            "line": invoice_line
        }
    )

def get_product_or_404(product_id: uuid.UUID, db: Session = Depends(get_db)) -> Product:
    product = product_crud.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/{invoice_id}/lines/{invoice_line_id}/link", response_class=HTMLResponse)
def product_link(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    db: Session = Depends(get_db),
    product_id: str = Form(default=""),
    new_product_name: str = Form(default="")
):
    if not product_id and not new_product_name: 
        raise HTTPException(status_code=400, detail="At least one parameter is required")
    
    if not product_id:
        product = product_crud.create(db, ProductCreate(name=new_product_name))
    else:
        product = get_product_or_404(uuid.UUID(product_id), db)

    invoice_line_crud.update(db, InvoiceLineUpdate(product_id=product.id), invoice_line)
    
    return templates.TemplateResponse(
        request=request, 
        name="invoices/partials/line_row.html",
        context={
            "invoice": invoice,
            "invoice_line": invoice_line,
        }
    )        

def get_serial_number_or_404(serial_number_id: uuid.UUID, db: Session = Depends(get_db)) -> SerialNumber:
    serial_number =serial_number_crud.get_by_id(db, serial_number_id)
    if not serial_number:
        raise HTTPException(status_code=404, detail="Serial number not found")
    return serial_number

def get_serials(invoice_line: InvoiceLine) -> list:
    if invoice_line.invoice.invoice_type == InvoiceType.sale:
        return invoice_line.sold_serials
    return invoice_line.purchased_serials


def toast_error(message: str) -> HTMLResponse:
    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": {"message": message , "type": "error"}})
    response.headers["HX-Reswap"] = "none"
    return response


@router.get("/{invoice_id}/lines/{invoice_line_id}/serials")
def serial_rows(
    request: Request,
    invoice_id: uuid.UUID, 
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
):

    if invoice_line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Invoice ID mismatch")
    
    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/serial_panel.html",
        context={
            "serials": get_serials(invoice_line),
            "invoice": invoice_line.invoice,
            "invoice_line": invoice_line
        }
    )

@router.post("/{invoice_id}/lines/{invoice_line_id}/serials")
def create_serial(
    request: Request,
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    db: Session = Depends(get_db),
    serial: str = Form(...),
):
    try:
        serial_number_service.add_serial_to_line(db, serial, invoice_line)
    except SerialValidationError as e:
        return toast_error(str(e))

    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/serial_panel.html",
        context={
            "serials": get_serials(invoice_line),
            "invoice": invoice_line.invoice,
            "invoice_line": invoice_line
        }
    )

@router.delete("/{invoice_id}/lines/{invoice_line_id}/serials/{serial_id}")    
def delete_serial(
    request: Request,
    serial_id: uuid.UUID,
    db: Session = Depends(get_db),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
):
    serial_number = get_serial_number_or_404(serial_id, db)
    
    try:
        serial_number_service.remove_serial_from_line(db, serial_number, invoice_line)
    except SerialValidationError as e:
        return toast_error(str(e))
    
    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/serial_panel.html",
        context={
            "serials": get_serials(invoice_line),
            "invoice": invoice_line.invoice,
            "invoice_line": invoice_line
        }
    )
