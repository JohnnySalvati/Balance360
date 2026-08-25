import datetime
import json
from decimal import Decimal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from balance360.crud import account as account_crud
from balance360.crud import category as category_crud
from balance360.crud import contact as contact_crud
from balance360.crud import entity as entity_crud
from balance360.crud import invoice as invoice_crud
from balance360.crud import invoice_line as invoice_line_crud
from balance360.crud import invoice_tribute as invoice_tribute_crud
from balance360.crud import product as product_crud
from balance360.crud import serial_number as serial_number_crud
from balance360.dependencies import Period, get_current_user, get_db, get_period
from balance360.enums import (
    Concepto,
    InvoiceType,
    IvaAliquot,
    SerialStatus,
    TributeType,
    VoucherType,
)
from balance360.exceptions import InvoicePaymentError, InvoicePrintError
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.models.invoice_tribute import InvoiceTribute
from balance360.models.product import Product
from balance360.models.serial_number import SerialNumber
from balance360.models.user import User
from balance360.schemas.invoice import InvoiceCreate, InvoiceUpdate
from balance360.schemas.invoice_line import InvoiceLineCreate, InvoiceLineUpdate
from balance360.schemas.invoice_tribute import InvoiceTributeCreate
from balance360.schemas.product import ProductCreate
from balance360.schemas.serial_number import SerialNumberUpdate
from balance360.services import invoice as invoice_service
from balance360.services import product_match
from balance360.services import product_match as product_match_service
from balance360.services import serial_number as serial_number_service
from balance360.services.invoice_pdf import build_qr
from balance360.web.responses import format_validation_error, toast_error
from balance360.web.templating import templates

router = APIRouter(prefix="/invoices")


def get_invoice_or_404(invoice_id: UUID, db: Session = Depends(get_db)) -> Invoice:
    invoice = invoice_crud.get_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


def get_invoice_line_or_404(invoice_line_id: UUID, db: Session = Depends(get_db)) -> InvoiceLine:
    invoice_line = invoice_line_crud.get_by_id(db, invoice_line_id)
    if not invoice_line:
        raise HTTPException(status_code=404, detail="Invoice line not found")
    return invoice_line


def get_serial_number_or_404(serial_number_id: UUID, db: Session = Depends(get_db)) -> SerialNumber:
    serial_number = serial_number_crud.get_by_id(db, serial_number_id)
    if not serial_number:
        raise HTTPException(status_code=404, detail="Serial number not found")
    return serial_number


def get_tribute_or_404(tribute_id: UUID, db: Session = Depends(get_db)) -> InvoiceTribute:
    invoice_tribute = invoice_tribute_crud.get_by_id(db, tribute_id)
    if not invoice_tribute:
        raise HTTPException(status_code=404, detail="Invoice tribute not found")
    return invoice_tribute


def get_product_or_404(product_id: UUID, db: Session = Depends(get_db)) -> Product:
    product = product_crud.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def get_invoice_line_serial_or_404(
    invoice: Invoice = Depends(get_invoice_or_404),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    serial_number: SerialNumber = Depends(get_serial_number_or_404),
    db: Session = Depends(get_db),
) -> SerialNumber:

    if invoice.invoice_type == InvoiceType.purchase:
        if serial_number.purchase_line_id != invoice_line.id:
            raise HTTPException(status_code=404, detail="Serial / invoice mismatch")
    else:
        if serial_number.sale_line_id != invoice_line.id:
            raise HTTPException(status_code=404, detail="Serial / invoice mismatch")
    if invoice_line.invoice_id != invoice.id:
        raise HTTPException(status_code=404, detail="Invoice / invoice line mismatch")

    return serial_number


@router.get("/", response_class=HTMLResponse)
def invoice_page(
    request: Request,
    db: Session = Depends(get_db),
    period: Period = Depends(get_period),
    entity_id: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    invoice_type: InvoiceType | None = None,
):
    user_entities = entity_crud.get_by_user(db, current_user.id)

    entity_ids = [UUID(entity_id)] if entity_id else [e.id for e in user_entities]

    filtered_invoices = invoice_crud.get_all(
        db=db, invoice_type=invoice_type, start=period.start, end=period.end, entity_ids=entity_ids
    )

    return templates.TemplateResponse(
        request=request,
        name="invoices/list.html",
        context={
            "period": period,
            "invoices": filtered_invoices,
            "current_type": invoice_type.value if invoice_type else None,
            "entities": user_entities,
            "selected_entity_id": entity_id,
        },
    )


@router.get("/fiscal-identities")
def fiscal_identities(request: Request, db: Session = Depends(get_db), entity_id: str = Query(...)):

    entity = entity_crud.get_by_id(db, UUID(entity_id))

    return templates.TemplateResponse(
        request=request,
        name="invoices/_fiscal_identity_options.html",
        context={
            "fiscal_identities": entity.fiscal_identities if entity else [],
            "selected_fiscal_identity_id": None,
        },
    )


@router.get("/new")
def new_invoice_form(request: Request, db: Session = Depends(get_db)):

    entities = entity_crud.get_all(db)

    return templates.TemplateResponse(
        request=request,
        name="invoices/new_form.html",
        context={
            "invoice_type": InvoiceType,
            "entities": entities,
            "fiscal_identities": entities[0].fiscal_identities if entities else [],
            "selected_fiscal_identity_id": None,
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "voucher_type": VoucherType,
            "concepto": Concepto,
        },
    )


@router.get("/{invoice_id}")
def invoice_detail(
    request: Request, invoice: Invoice = Depends(get_invoice_or_404), db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        request=request,
        name="invoices/detail.html",
        context={
            "invoice": invoice,
            "accounts": account_crud.get_all(db),
            "iva_aliquots": IvaAliquot,
            "tribute_types": TributeType,
        },
    )


@router.post("/", response_class=HTMLResponse)
def create_invoice(
    db: Session = Depends(get_db),
    invoice_type: str = Form(...),
    entity_id: str = Form(...),
    fiscal_identity_id: str | None = Form(default=""),
    contact_id: str = Form(...),
    category_id: str | None = Form(default=""),
    date: str = Form(...),
    formal: bool | None = Form(default=False),
    tax_only: bool | None = Form(default=False),
    voucher_type: str | None = Form(default=""),
    pos: str | None = Form(default=""),
    number: str | None = Form(default=""),
    pdf_lines: str | None = Form(default=""),
    concepto: str | None = Form(default=""),
    from_date: str | None = Form(default=""),
    to_date: str | None = Form(default=""),
    due_date: str | None = Form(default=""),
):
    try:
        data = InvoiceCreate(
            invoice_type=InvoiceType(invoice_type),
            entity_id=UUID(entity_id),
            fiscal_identity_id=UUID(fiscal_identity_id) if fiscal_identity_id else None,
            contact_id=UUID(contact_id),
            category_id=UUID(category_id) if category_id else None,
            date=datetime.date.fromisoformat(date),
            formal=formal if formal else False,
            tax_only=tax_only if tax_only else False,
            voucher_type=VoucherType(voucher_type) if voucher_type else None,
            pos=int(pos) if pos else None,
            number=int(number) if number else None,
            concepto=Concepto(concepto) if concepto else Concepto.products,
            from_date=datetime.date.fromisoformat(from_date) if from_date else None,
            to_date=datetime.date.fromisoformat(to_date) if to_date else None,
            due_date=datetime.date.fromisoformat(due_date) if due_date else None,
        )
        invoice = invoice_crud.create(db, data)
        invoice_service.normalize_fields_by_formality(invoice)

        if pdf_lines:
            products = product_crud.get_all(db)  # cargar el catálogo una sola vez
            for line in json.loads(pdf_lines):
                iva_rate = Decimal(line["iva_rate"])
                # mapear la tasa al enum
                aliquot = next((a for a in IvaAliquot if a.rate == iva_rate), IvaAliquot.standard)
                # auto-vincular el producto solo si el match es muy fuerte;
                # el resto queda sin producto para revisar en el borrador.
                match = product_match.best_match(line["description"], products)
                product_id = (
                    match.product.id
                    if match and match.score >= product_match.AUTO_ACCEPT_SCORE
                    else None
                )
                invoice_line_crud.create(
                    db,
                    InvoiceLineCreate(
                        invoice_id=invoice.id,
                        product_id=product_id,
                        description=line["description"] or None,
                        quantity=int(Decimal(line["quantity"])),
                        unit_price=Decimal(line["unit_price"]),
                        iva_aliquot=aliquot,
                    ),
                )
    except ValidationError as e:
        return HTMLResponse(f'<p class="text-red-600 text-sm">{format_validation_error(e)}</p>')
    except ValueError as e:
        return HTMLResponse(f'<p class="text-red-600 text-sm">{e}</p>')
    return Response(status_code=200, headers={"HX-Redirect": f"/invoices/{invoice.id}"})


@router.patch("/{invoice_id}", response_class=HTMLResponse)
def update_invoice(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
    invoice_type: str | None = Form(default=""),
    entity_id: str | None = Form(default=""),
    fiscal_identity_id: str | None = Form(default=""),
    contact_id: str | None = Form(default=""),
    category_id: str | None = Form(default=""),
    date: str | None = Form(default=""),
    formal: bool | None = Form(default=None),
    tax_only: bool | None = Form(default=None),
    voucher_type: str | None = Form(default=""),
    pos: str | None = Form(default=""),
    number: str | None = Form(default=""),
    concepto: str | None = Form(default=""),
    from_date: str | None = Form(default=""),
    to_date: str | None = Form(default=""),
    due_date: str | None = Form(default=""),
):
    if invoice.confirmed:
        raise HTTPException(status_code=404, detail="Invoice confirmed")
    try:
        data = InvoiceUpdate(
            invoice_type=InvoiceType(invoice_type) if invoice_type else None,
            entity_id=UUID(entity_id) if entity_id else None,
            fiscal_identity_id=UUID(fiscal_identity_id) if fiscal_identity_id else None,
            contact_id=UUID(contact_id) if contact_id else None,
            category_id=UUID(category_id) if category_id else None,
            date=datetime.date.fromisoformat(date) if date else None,
            formal=bool(formal),
            tax_only=bool(tax_only),
            voucher_type=VoucherType(voucher_type) if voucher_type else None,
            pos=int(pos) if pos else None,
            number=int(number) if number else None,
            concepto=Concepto(concepto) if concepto else Concepto.products,
            from_date=datetime.date.fromisoformat(from_date) if from_date else None,
            to_date=datetime.date.fromisoformat(to_date) if to_date else None,
            due_date=datetime.date.fromisoformat(due_date) if due_date else None,
        )
    except ValidationError as e:
        return toast_error(format_validation_error(e))
    except ValueError as e:
        return toast_error(str(e))

    invoice = invoice_crud.update(db, data, invoice)
    invoice_service.normalize_fields_by_formality(invoice)

    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/header_saved.html",
        context={"invoice": invoice, "iva_aliquots": IvaAliquot},
    )


@router.get("/{invoice_id}/lines/new-form", response_class=HTMLResponse)
def new_line_form(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
):

    suggestions = {}
    products = product_crud.get_all(db)

    for product in products:
        invoice_line = invoice_line_crud.get_by_last_product_purchase(
            db, product.id, invoice.entity_id
        )
        if invoice_line:
            suggestions[invoice_line.product_id] = {
                "price": invoice_line.unit_price * (1 + product.margin / 100),
                "iva": invoice_line.iva_aliquot.name,
            }

    return templates.TemplateResponse(
        request=request,
        name="invoices/new_line_form.html",
        context={
            "invoice": invoice,
            "products": products,
            "iva_aliquots": IvaAliquot,
            "suggestions": suggestions,
        },
    )


@router.delete("/{invoice_id}/lines/{invoice_line_id}", response_class=HTMLResponse)
def delete_invoice_line(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    db: Session = Depends(get_db),
):
    if invoice_line.invoice.id != invoice.id:
        raise HTTPException(status_code=404, detail="Invoice line mistmach invoice")

    invoice_line_crud.delete(db, invoice_line)

    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/items_table.html",
        context={"invoice": invoice, "iva_aliquots": IvaAliquot},
    )


@router.post("/{invoice_id}/confirm", response_class=HTMLResponse)
def confirm_invoice(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
):
    invoice_service.confirm_invoice(db, invoice)
    return Response(status_code=200, headers={"HX-Redirect": f"/invoices/{invoice.id}"})


@router.post("/{invoice_id}/unconfirm", response_class=HTMLResponse)
def unconfirm_invoice(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
):
    invoice_service.unconfirm_invoice(db, invoice)
    return Response(status_code=200, headers={"HX-Redirect": f"/invoices/{invoice.id}"})


@router.post("/{invoice_id}/pay", response_class=HTMLResponse)
def pay_invoice(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
    account_id: str = Form(...),
    payment_date: str = Form(...),
):

    account = account_crud.get_by_id(db, UUID(account_id))
    if not account:
        raise InvoicePaymentError("Cuenta no encontrada")

    invoice_service.register_payment(
        db, invoice, account, datetime.date.fromisoformat(payment_date)
    )

    return Response(status_code=200, headers={"HX-Redirect": f"/invoices/{invoice.id}"})


@router.post("/{invoice_id}/lines", response_class=HTMLResponse)
def create_invoice_line(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
    product_id: str | None = Form(default=""),
    description: str | None = Form(default=""),
    quantity: str = Form(...),
    unit_price: str = Form(...),
    iva_aliquot: str = Form(...),
):
    product_id_parsed = UUID(product_id) if product_id else None
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

    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/items_table.html",
        context={"invoice": invoice, "iva_aliquots": IvaAliquot},
    )


@router.post("/{invoice_id}/authorize", response_class=HTMLResponse)
def authorize_invoice(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
):
    invoice_service.authorize_invoice(db, invoice)
    return Response(status_code=200, headers={"HX-Redirect": f"/invoices/{invoice.id}"})


@router.get("/{invoice_id}/lines/close-form", response_class=HTMLResponse)
def close_line_form(invoice_id: UUID):
    return HTMLResponse("")


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
        },
    )


@router.post("/{invoice_id}/tributes", response_class=HTMLResponse)
def create_invoice_tribute(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
    tribute_type: str = Form(...),
    description: str = Form(...),
    base_amount: str = Form(...),
    rate: str = Form(...),
):
    try:
        data = InvoiceTributeCreate(
            invoice_id=invoice.id,
            tribute_type=TributeType[tribute_type],
            description=description,
            base_amount=Decimal(base_amount),
            rate=Decimal(rate),
        )
        invoice_tribute_crud.create(db, data)
    except ValidationError as e:
        return toast_error(format_validation_error(e))

    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/items_table.html",
        context={"invoice": invoice, "iva_aliquots": IvaAliquot},
    )


@router.delete("/{invoice_id}/tributes/{tribute_id}", response_class=HTMLResponse)
def delete_invoice_tribute(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    tribute: InvoiceTribute = Depends(get_tribute_or_404),
    db: Session = Depends(get_db),
):
    if tribute.invoice_id != invoice.id:
        raise HTTPException(status_code=404, detail="Invoice tribute mistmach invoice")

    invoice_tribute_crud.delete(db, tribute)
    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/items_table.html",
        context={"invoice": invoice, "iva_aliquots": IvaAliquot},
    )


@router.get("/{invoice_id}/tributes/close-form", response_class=HTMLResponse)
def close_tribute_form(invoice_id: UUID):
    return HTMLResponse("")


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
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "iva_rate": str(line.iva_rate),
            }
            for line in parsed.lines
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
    from balance360.enums import CondicionIva, ContactType, DocType
    from balance360.schemas.contact import ContactCreate

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
def delete_invoice(invoice: Invoice = Depends(get_invoice_or_404), db: Session = Depends(get_db)):
    invoice_crud.delete(db, invoice)
    return HTMLResponse("")


@router.get("/{invoice_id}/header", response_class=HTMLResponse)
def invoice_header_display(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
):
    return templates.TemplateResponse(
        request=request, name="invoices/partials/header_display.html", context={"invoice": invoice}
    )


@router.get("/{invoice_id}/header-form", response_class=HTMLResponse)
def invoice_header_form(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
    focus: str = Query(default=""),
):
    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/header_form.html",
        context={
            "invoice": invoice,
            "invoice_type": InvoiceType,
            "entities": entity_crud.get_all(db),
            "fiscal_identities": invoice.entity.fiscal_identities,
            "selected_fiscal_identity_id": invoice.fiscal_identity_id,
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "voucher_type": VoucherType,
            "concepto": Concepto,
            "focus": focus,
        },
    )


@router.get("/{invoice_id}/lines/{invoice_line_id}/match-form", response_class=HTMLResponse)
def match_product_suggestions(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    db: Session = Depends(get_db),
):
    suggestions = product_match_service.suggest(
        invoice_line.description, product_crud.get_all(db), limit=5
    )

    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/match_form.html",
        context={"suggestions": suggestions, "invoice": invoice, "line": invoice_line},
    )


@router.post("/{invoice_id}/lines/{invoice_line_id}/link", response_class=HTMLResponse)
def product_link(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    db: Session = Depends(get_db),
    product_id: str = Form(default=""),
    track_serial: bool = Form(default=True),
    new_product_name: str = Form(default=""),
):
    if not product_id and not new_product_name:
        raise HTTPException(status_code=400, detail="At least one parameter is required")

    if not product_id:
        product = product_crud.create(
            db, ProductCreate(name=new_product_name, track_serial=track_serial)
        )
    else:
        product = get_product_or_404(UUID(product_id), db)

    invoice_line_crud.update(db, InvoiceLineUpdate(product_id=product.id), invoice_line)

    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/line_row.html",
        context={
            "invoice": invoice,
            "invoice_line": invoice_line,
        },
    )


def get_serials(invoice_line: InvoiceLine) -> list:
    if invoice_line.invoice.invoice_type == InvoiceType.sale:
        return invoice_line.sold_serials
    return invoice_line.purchased_serials


@router.get("/{invoice_id}/lines/{invoice_line_id}/serials")
def serial_rows(
    request: Request,
    invoice_id: UUID,
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
            "invoice_line": invoice_line,
        },
    )


@router.post("/{invoice_id}/lines/{invoice_line_id}/serials")
def create_serial(
    request: Request,
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    db: Session = Depends(get_db),
    serial: str = Form(...),
):
    serial_number_service.add_serial_to_line(db, serial, invoice_line)

    if invoice_line.invoice.invoice_type == InvoiceType.sale:
        return templates.TemplateResponse(
            request=request,
            name="invoices/partials/items_table.html",
            context={"invoice": invoice_line.invoice, "iva_aliquots": IvaAliquot},
        )
    else:
        return templates.TemplateResponse(
            request=request,
            name="invoices/partials/serial_panel.html",
            context={
                "serials": get_serials(invoice_line),
                "invoice": invoice_line.invoice,
                "invoice_line": invoice_line,
            },
        )


@router.delete("/{invoice_id}/lines/{invoice_line_id}/serials/{serial_number_id}")
def delete_serial(
    request: Request,
    db: Session = Depends(get_db),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    serial_number: SerialNumber = Depends(get_invoice_line_serial_or_404),
):
    serial_number_service.remove_serial_from_line(db, serial_number, invoice_line)

    if invoice_line.invoice.invoice_type == InvoiceType.sale:
        response = templates.TemplateResponse(
            request=request,
            name="invoices/partials/items_table.html",
            context={"invoice": invoice_line.invoice, "iva_aliquots": IvaAliquot},
        )
    else:
        response = templates.TemplateResponse(
            request=request,
            name="invoices/partials/serial_panel.html",
            context={
                "serials": get_serials(invoice_line),
                "invoice": invoice_line.invoice,
                "invoice_line": invoice_line,
            },
        )
    return response


@router.post("/{invoice_id}/scan-serial")
def scan_serial(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    serial: str = Form(...),
    db: Session = Depends(get_db),
):
    if invoice.invoice_type == InvoiceType.purchase or invoice.confirmed:
        return toast_error("Comprobante invalido")

    serial_number = serial_number_crud.get_by_serial(db, serial)
    if not serial_number:
        return toast_error("Serial inexistente")

    if serial_number.status != SerialStatus.available:
        return toast_error("El serial no esta disponible")

    if invoice.entity_id != serial_number.purchase_line.invoice.entity_id:
        return toast_error("El serial no fue comprado por esta entidad")

    invoice_line = invoice_line_crud.get_by_invoice_product(
        db, invoice.id, serial_number.product_id
    )

    if not invoice_line:
        invoice_line = invoice_line_crud.create(
            db,
            InvoiceLineCreate(
                invoice_id=invoice.id,
                product_id=serial_number.product_id,
                quantity=1,
                unit_price=serial_number.purchase_line.unit_price
                * (1 + serial_number.product.margin / 100),
                iva_aliquot=serial_number.purchase_line.iva_aliquot,
            ),
        )

    serial_number_crud.update(
        db,
        serial_number,
        SerialNumberUpdate(sale_line_id=invoice_line.id, status=SerialStatus.reserved),
    )

    invoice_line_crud.update(
        db, InvoiceLineUpdate(quantity=len(invoice_line.sold_serials)), invoice_line
    )

    return Response(status_code=200, headers={"HX-Redirect": f"/invoices/{invoice.id}"})


@router.patch("/{invoice_id}/lines/{invoice_line_id}")
def update_lines(
    request: Request,
    invoice: Invoice = Depends(get_invoice_or_404),
    invoice_line: InvoiceLine = Depends(get_invoice_line_or_404),
    unit_price: str = Form(default=""),
    iva_aliquot: str = Form(default=""),
    description: str = Form(default=""),
    quantity: str = Form(default=""),
    db: Session = Depends(get_db),
):
    if invoice.confirmed:
        raise HTTPException(status_code=404, detail="Invoice confirmed")

    if invoice.id != invoice_line.invoice_id:
        raise HTTPException(status_code=404, detail="Invoice / line ID mismatch")

    try:
        fields = {}
        if unit_price:
            fields["unit_price"] = Decimal(unit_price)
        if iva_aliquot:
            fields["iva_aliquot"] = IvaAliquot[iva_aliquot]
        if description:
            fields["description"] = description
        if quantity:
            fields["quantity"] = int(quantity)
        data = InvoiceLineUpdate(**fields)

    except ValidationError as e:
        return toast_error(format_validation_error(e))
    except ArithmeticError as e:
        return toast_error(str(e))
    except ValueError as e:
        return toast_error(str(e))

    invoice_line_crud.update(db, data, invoice_line)

    return templates.TemplateResponse(
        request=request,
        name="invoices/partials/items_table.html",
        context={"invoice": invoice, "iva_aliquots": IvaAliquot},
    )


@router.get("/{invoice_id}/pdf")
def download_pdf(
    invoice: Invoice = Depends(get_invoice_or_404),
):
    if not invoice.is_printable:
        raise InvoicePrintError("El comprobante no es IMPRIMIBLE")

    qr = build_qr(invoice)

    html = templates.get_template("invoices/pdf.html").render({"invoice": invoice, "qr": qr})

    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return HTMLResponse(html)  # dev local sin GTK → preview HTML
    return Response(
        content=HTML(string=html).write_pdf(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="comprobante.pdf"'},
    )


@router.get("/{invoice_id}/render")
def render_invoice_pdf(
    invoice: Invoice = Depends(get_invoice_or_404),
):
    if not invoice.is_printable:
        raise InvoicePrintError("El comprobante no es IMPRIMIBLE")

    qr = build_qr(invoice)

    html = templates.get_template("invoices/pdf.html").render({"invoice": invoice, "qr": qr})

    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return toast_error("No se pudo generar el PDF")  # dev local sin GTK → raises
    return Response(
        content=HTML(string=html).write_pdf(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="comprobante.pdf"'},
    )


@router.post("/{invoice_id}/credit-note")
def create_credit_note(
    invoice: Invoice = Depends(get_invoice_or_404),
    db: Session = Depends(get_db),
):
    nc = invoice_service.create_credit_note(db=db, original=invoice)

    return Response(status_code=200, headers={"HX-Redirect": f"/invoices/{nc.id}"})
