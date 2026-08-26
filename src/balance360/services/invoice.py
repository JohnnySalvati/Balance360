from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from balance360.crud import invoice as invoice_crud
from balance360.crud import invoice_line as invoice_line_crud
from balance360.crud import transaction as transaction_crud
from balance360.dtos.auth import Auth
from balance360.dtos.invoice_request import (
    AssociatedVoucher,
    InvoiceRequest,
    IvaDetail,
    Tribute,
    VoucherData,
    VoucherInfo,
)
from balance360.enums import (
    Concepto,
    CondicionIva,
    DocType,
    InvoiceType,
    SerialStatus,
    TransactionType,
    VoucherType,
)
from balance360.exceptions import (
    InvoiceAuthorizationError,
    InvoiceConfirmationError,
    InvoiceCreditNoteError,
    InvoiceDeleteError,
    InvoicePaymentError,
    InvoiceRequestError,
)
from balance360.models.account import Account
from balance360.models.invoice import Invoice
from balance360.models.serial_number import SerialNumber
from balance360.schemas.invoice import InvoiceCreate
from balance360.schemas.invoice_line import InvoiceLineCreate
from balance360.schemas.transaction import TransactionCreate
from balance360.services.arca import get_access_ticket
from balance360.services.stock import get_product_stock
from balance360.services.text import digits_only
from balance360.services.wsfe import authorize_invoice as wsfe_authorize_invoice


def confirm_invoice(db: Session, invoice: Invoice):
    validate_confirmation(db, invoice)
    invoice.confirmed = True

    if invoice.is_nc:
        # Una NC cargada a mano desde el portal de ARCA no tiene comprobante
        # relacionado: es un estado valido y no hay seriales que mover.
        if invoice.related_invoice is not None:
            for invoice_line in invoice.related_invoice.invoice_lines:
                if invoice.invoice_type == InvoiceType.purchase:
                    for serial in invoice_line.purchased_serials:
                        serial.status = SerialStatus.returned
                else:
                    for serial in invoice_line.sold_serials:
                        serial.status = SerialStatus.available
                        serial.sale_line_id = None
    else:
        for invoice_line in invoice.invoice_lines:
            if not invoice_line.product or not invoice_line.product.track_serial:
                continue
            if invoice.invoice_type == InvoiceType.purchase:
                for serial in invoice_line.purchased_serials:
                    serial.status = SerialStatus.available
            else:
                for serial in invoice_line.sold_serials:
                    serial.status = SerialStatus.sold

    db.flush()


def unconfirm_invoice(db: Session, invoice: Invoice):
    validate_unconfirmation(invoice)
    invoice.confirmed = False

    if invoice.is_nc:
        if invoice.related_invoice is not None:
            for invoice_line in invoice.related_invoice.invoice_lines:
                if not invoice_line.product or not invoice_line.product.track_serial:
                    continue
                if invoice.related_invoice.invoice_type == InvoiceType.purchase:
                    for serial in invoice_line.purchased_serials:
                        serial.status = SerialStatus.available
                #  The else branch is unreachable on purpose by validate_unconfirmation.
                #  The reason in Pending.md
    else:
        for invoice_line in invoice.invoice_lines:
            if not invoice_line.product or not invoice_line.product.track_serial:
                continue
            if invoice.invoice_type == InvoiceType.purchase:
                for serial in invoice_line.purchased_serials:
                    serial.status = SerialStatus.pending
            else:
                for serial in invoice_line.sold_serials:
                    serial.status = SerialStatus.reserved
    db.flush()


def register_payment(db: Session, invoice: Invoice, account: Account, payment_date: date):

    validate_payment(invoice)
    ref = f"{invoice.pos}-{invoice.number}" if invoice.formal else "informal"

    data = TransactionCreate(
        date=payment_date,
        description=(
            f"{'Compra' if invoice.invoice_type == InvoiceType.purchase else 'Venta'}"
            f" {ref} {invoice.contact.name}"
        ),
        amount=invoice.total,
        type=TransactionType.expense
        if invoice.invoice_type == InvoiceType.purchase
        else TransactionType.income,
        account_id=account.id,
        entity_id=invoice.entity_id,
        contact_id=invoice.contact_id,
        category_id=invoice.category_id,
        invoice_id=invoice.id,
        is_manual=True,
        is_transfer=False,
    )
    transaction_crud.create(db, data)
    invoice.paid = True
    db.flush()


def delete_invoice(db: Session, invoice: Invoice):

    validate_delete(invoice)

    for invoice_line in invoice.invoice_lines:
        if not invoice_line.product or not invoice_line.product.track_serial:
            continue
        if invoice.invoice_type == InvoiceType.sale:
            for serial in invoice_line.sold_serials:
                serial.status = SerialStatus.available
                serial.sale_line_id = None

    invoice_crud.delete(db, invoice)
    db.flush()


def _build_invoice_request(invoice: Invoice) -> InvoiceRequest:
    ticket = get_access_ticket("wsfe")
    token = ticket["token"]
    sign = ticket["sign"]

    assert invoice.fiscal_identity
    assert invoice.fiscal_identity.tax_id
    assert invoice.pos
    assert invoice.voucher_type

    auth = Auth(cuit=invoice.fiscal_identity.tax_id, token=token, sign=sign)

    voucher_info = VoucherInfo(pos=invoice.pos, voucher_type=invoice.voucher_type)

    iva_detail = [
        IvaDetail(id=item.aliquot.arca_code, base_imp=item.net_amount, amount=item.iva_amount)
        for item in invoice.iva_breakdown
    ]

    tributes = [
        Tribute(
            id=tribute.tribute_type.value,
            description=tribute.description,
            base_imp=tribute.base_amount,
            aliquot=tribute.rate,
            amount=tribute.amount,
        )
        for tribute in invoice.invoice_tributes
    ]

    if invoice.is_nc:
        valid_vouchers = {
            VoucherType.NCA: VoucherType.A,
            VoucherType.NCB: VoucherType.B,
            VoucherType.NCC: VoucherType.C,
        }

        if not invoice.related_invoice:
            raise InvoiceRequestError("La NC no tiene comprobante asociado")

        if valid_vouchers[invoice.voucher_type] != invoice.related_invoice.voucher_type:
            raise InvoiceRequestError(
                f"""Para una {invoice.voucher_type}
                  se espera una factura {valid_vouchers[invoice.voucher_type]}"""
            )

        assert invoice.related_invoice.voucher_type
        assert invoice.related_invoice.pos
        assert invoice.related_invoice.number
        assert invoice.related_invoice.fiscal_identity
        assert invoice.related_invoice.fiscal_identity.tax_id

        associated_vouchers = [
            AssociatedVoucher(
                tipo=invoice.related_invoice.voucher_type.arca_code,
                pos=invoice.related_invoice.pos,
                number=invoice.related_invoice.number,
                cuit=int(invoice.related_invoice.fiscal_identity.tax_id),
                date=invoice.related_invoice.date,
            )
        ]
    else:
        associated_vouchers = []

    voucher_data = VoucherData(
        date=invoice.date,
        receiver_condicion_iva=invoice.contact.condicion_iva,
        receiver_doc_type=invoice.contact.doc_type,
        receiver_doc_number=int(digits_only(invoice.contact.tax_id) or "0"),
        iva_detail=iva_detail if invoice.applies_iva else None,
        tributes=tributes,
        total=invoice.total,
        concepto=invoice.concepto,
        from_date=invoice.from_date,
        to_date=invoice.to_date,
        due_date=invoice.due_date,
        associated_vouchers=associated_vouchers,
    )

    invoice_request = InvoiceRequest(
        auth=auth, voucher_info=voucher_info, voucher_data=voucher_data
    )
    return invoice_request


def authorize_invoice(db: Session, invoice: Invoice):
    validate_authorization(invoice)

    invoice_request = _build_invoice_request(invoice)

    result = wsfe_authorize_invoice(invoice_request)

    invoice.cae = result.cae
    invoice.cae_expiry = result.expiration
    invoice.number = result.number
    invoice.authorized = True
    db.flush()


def validate_authorization(invoice: Invoice):
    if not invoice.fiscal_identity:
        raise InvoiceAuthorizationError(
            "El comprobante no tiene una identidad fiscal emisora asignada"
        )

    if not invoice.fiscal_identity.tax_id:
        raise InvoiceAuthorizationError("La identidad fiscal no posee CUIT")

    if not invoice.pos or not invoice.voucher_type:
        raise InvoiceAuthorizationError("El tipo y punto de venta del comprobante son obligatorios")

    if invoice.contact.doc_type != DocType.FINAL and not invoice.contact.tax_id:
        raise InvoiceAuthorizationError("Se necesita numero de CUIT del cliente")

    if not invoice.confirmed:
        raise InvoiceAuthorizationError("El comprobante no esta confirmado")

    if invoice.authorized:
        raise InvoiceAuthorizationError("El comprobante ya esta autorizado")

    if invoice.invoice_type == InvoiceType.purchase:
        raise InvoiceAuthorizationError("No se puede autorizar una compra")

    if invoice.concepto is not Concepto.products:
        if not (invoice.from_date and invoice.to_date and invoice.due_date):
            raise InvoiceAuthorizationError("Las tres fechas son requeridas")
        margin = 10
    else:
        margin = 5

    today = date.today()
    if invoice.date > today + timedelta(days=margin) or invoice.date < today - timedelta(
        days=margin
    ):
        raise InvoiceAuthorizationError(f"Fecha fuera del rango de +-{margin} dias")


def allowed_for(invoice: Invoice) -> set[VoucherType]:
    issuer_allowed = {
        CondicionIva.INSCRIPTO: {VoucherType.A, VoucherType.B, VoucherType.NCA, VoucherType.NCB},
        CondicionIva.MONOTRIBUTO: {VoucherType.C, VoucherType.NCC},
        CondicionIva.EXENTO: {VoucherType.C, VoucherType.NCC},
        CondicionIva.FINAL: set(),
    }
    receiver_allowed = {
        CondicionIva.EXENTO: {VoucherType.B, VoucherType.NCB, VoucherType.C, VoucherType.NCC},
        CondicionIva.FINAL: {VoucherType.B, VoucherType.NCB, VoucherType.C, VoucherType.NCC},
        CondicionIva.INSCRIPTO: {VoucherType.A, VoucherType.NCA, VoucherType.C, VoucherType.NCC},
        CondicionIva.MONOTRIBUTO: {VoucherType.B, VoucherType.NCB, VoucherType.C, VoucherType.NCC},
    }

    if not invoice.fiscal_identity:
        return set()

    if invoice.invoice_type == InvoiceType.purchase:
        issuer_condicion = invoice.contact.condicion_iva
        receiver_condicion = invoice.fiscal_identity.condicion_iva
    else:
        issuer_condicion = invoice.fiscal_identity.condicion_iva
        receiver_condicion = invoice.contact.condicion_iva

    return issuer_allowed[issuer_condicion] & receiver_allowed[receiver_condicion]


# Un mismo estado esperado se explica igual en todos los mensajes, asi que el texto
# vive en un solo lugar y no repetido en cada validacion.
_SERIAL_STATUS_ERROR = {
    SerialStatus.available: "no esta disponible",
    SerialStatus.reserved: "no esta reservado",
    SerialStatus.sold: "no esta vendido",
    SerialStatus.pending: "no esta pendiente de confirmacion",
    SerialStatus.returned: "no ha sido devuelto",
}


def _wrong_status_error(serial: SerialNumber, required: SerialStatus) -> InvoiceConfirmationError:
    return InvoiceConfirmationError(f"El serial {serial.serial} {_SERIAL_STATUS_ERROR[required]}")


def validate_confirmation(db: Session, invoice: Invoice) -> None:
    if invoice.confirmed:
        raise InvoiceConfirmationError("El comprobante ya esta confirmado")

    if not invoice.invoice_lines:
        raise InvoiceConfirmationError("El comprobante no tiene items")

    if invoice.tax_only and invoice.invoice_type == InvoiceType.sale:
        raise InvoiceConfirmationError(
            "Un comprobante no puede ser venta y solo impositivo simultaneamente"
        )

    _validate_formality(invoice)

    # Una NC no mueve sus propias lineas: deshace las del comprobante original.
    if invoice.is_nc:
        _validate_credit_note(db, invoice)
    else:
        _validate_lines(db, invoice)


def _validate_formality(invoice: Invoice) -> None:
    """Numeracion e identidad fiscal si es formal; ausencia de IVA si no lo es."""
    if not invoice.formal:
        if invoice.tax_only:
            raise InvoiceConfirmationError(
                "Un comprobante no puede ser informal y solo impositivo simultaneamente"
            )
        if any(line.iva_rate != Decimal(0) for line in invoice.invoice_lines):
            raise InvoiceConfirmationError(
                "Los items de un comprobante informal no pueden contener IVA"
            )
        return

    if not invoice.pos:
        raise InvoiceConfirmationError("Se necesita punto de venta")
    # En una venta el numero lo asigna ARCA al autorizar; en una compra ya viene impreso.
    if invoice.invoice_type == InvoiceType.purchase and not invoice.number:
        raise InvoiceConfirmationError("Se necesita numero de comprobante")
    if invoice.fiscal_identity is None:
        raise InvoiceConfirmationError("Se necesita identidad fiscal")
    if invoice.voucher_type not in allowed_for(invoice):
        raise InvoiceConfirmationError("Tipo de comprobante no admitido")


def _validate_credit_note(db: Session, invoice: Invoice) -> None:
    """Una NC se valida contra el comprobante original, no contra sus propias lineas."""
    original = invoice.related_invoice
    if original is None:
        return

    if invoice.invoice_type == InvoiceType.purchase:
        # Devolver al proveedor saca unidades del deposito: tienen que estar.
        _validate_stock(db, original, invoice.entity_id)
        ensure_serials_have_status(original, SerialStatus.available)
    else:
        ensure_serials_have_status(original, SerialStatus.sold)


def _validate_stock(db: Session, source: Invoice, entity_id: UUID) -> None:
    """Stock suficiente para los productos de `source` que no llevan seriales.

    Los que llevan seriales no se cuentan por stock sino por serial, en _validate_lines.
    """
    for line in source.invoice_lines:
        if not line.product or line.product.track_serial:
            continue
        if get_product_stock(db, line.product.id, entity_id) < line.quantity:
            raise InvoiceConfirmationError(f"Stock insuficiente de {line.product.name}")


def _validate_lines(db: Session, invoice: Invoice) -> None:
    """Comprobante normal: cada linea con producto tiene que ser entregable."""
    is_sale = invoice.invoice_type == InvoiceType.sale
    required = SerialStatus.reserved if is_sale else SerialStatus.pending

    if is_sale:
        _validate_stock(db, invoice, invoice.entity_id)

    for line in invoice.invoice_lines:
        if not line.product or not line.product.track_serial:
            continue

        serials = line.sold_serials if is_sale else line.purchased_serials
        if line.quantity != len(serials):
            raise InvoiceConfirmationError(f"Cantidad erronea de seriales para {line.product.name}")

        for serial in serials:
            if serial.product_id != line.product_id:
                raise InvoiceConfirmationError("El serial no corresponde a este producto")
            if serial.status != required:
                raise _wrong_status_error(serial, required)
            if is_sale and serial.purchase_line.invoice.entity_id != invoice.entity_id:
                raise InvoiceConfirmationError("El serial no fue comprado por esta entidad")


def validate_payment(invoice: Invoice):
    if invoice.is_nc:
        raise InvoicePaymentError("No se puede registrar un pago para una NC")
    if not invoice.confirmed:
        raise InvoicePaymentError("El comprobante no esta confirmado")
    if invoice.paid:
        raise InvoicePaymentError("El comprobante ya esta pago")


def validate_delete(invoice: Invoice):
    if invoice.confirmed:
        raise InvoiceDeleteError("El comprobante esta confirmado")


def ensure_serials_have_status(invoice: Invoice, required_status: SerialStatus) -> None:
    is_purchase = invoice.invoice_type == InvoiceType.purchase
    for invoice_line in invoice.invoice_lines:
        if not invoice_line.product or not invoice_line.product.track_serial:
            continue
        for serial in invoice_line.purchased_serials if is_purchase else invoice_line.sold_serials:
            if serial.status != required_status:
                raise _wrong_status_error(serial, required_status)


def validate_unconfirmation(invoice: Invoice):
    if not invoice.confirmed:
        raise InvoiceConfirmationError("El comprobante no esta confirmado")
    if invoice.paid:
        raise InvoiceConfirmationError("El comprobante tiene pago asociado")
    if invoice.authorized:
        raise InvoiceConfirmationError("El comprobante esta autorizado CAE")
    if invoice.is_nc:
        if invoice.related_invoice is not None:
            if invoice.invoice_type == InvoiceType.purchase:
                ensure_serials_have_status(invoice.related_invoice, SerialStatus.returned)
            else:
                for invoice_line in invoice.related_invoice.invoice_lines:
                    if invoice_line.product and invoice_line.product.track_serial:
                        raise InvoiceConfirmationError(
                            "No se puede desconfirmar una NC de una venta"
                        )
    else:
        if invoice.invoice_type == InvoiceType.purchase:
            ensure_serials_have_status(invoice, SerialStatus.available)
        else:
            ensure_serials_have_status(invoice, SerialStatus.sold)


def create_credit_note(db: Session, original: Invoice):
    if original.related_credit_notes:
        raise InvoiceCreditNoteError("El comprobante ya tiene una nota de crédito")
    if original.invoice_type == InvoiceType.sale:
        if not original.authorized:
            raise InvoiceCreditNoteError("El comprobante original no esta autorizado")
    else:
        if not original.confirmed:
            raise InvoiceCreditNoteError("El comprobante original no esta confirmado")

    assert original.voucher_type

    invoice_letter = {
        VoucherType.A: VoucherType.NCA,
        VoucherType.B: VoucherType.NCB,
        VoucherType.C: VoucherType.NCC,
    }

    data = InvoiceCreate(
        invoice_type=original.invoice_type,
        entity_id=original.entity_id,
        contact_id=original.contact_id,
        category_id=original.category_id,
        date=date.today(),
        formal=original.formal,
        tax_only=original.tax_only,
        voucher_type=invoice_letter[original.voucher_type],
        pos=original.pos,
        confirmed=False,
        paid=False,
        authorized=False,
        concepto=original.concepto,
        from_date=original.from_date,
        to_date=original.to_date,
        due_date=original.due_date,
        related_invoice_id=original.id,
    )

    nc_invoice = invoice_crud.create(db, data)

    nc_invoice.fiscal_identity_id = original.fiscal_identity_id

    for line in original.invoice_lines:
        data = InvoiceLineCreate(
            invoice_id=nc_invoice.id,
            product_id=line.product_id,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            iva_aliquot=line.iva_aliquot,
        )

        invoice_line_crud.create(db, data)

    return nc_invoice


def normalize_fields_by_formality(invoice: Invoice) -> None:
    if not invoice.formal:
        invoice.voucher_type = None
        invoice.pos = None
        invoice.number = None
        invoice.fiscal_identity_id = None
        invoice.from_date = None
        invoice.to_date = None
        invoice.due_date = None
        invoice.concepto = Concepto.products
