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
    InvoiceFulfillmentError,
    InvoicePaymentError,
    InvoiceRequestError,
)
from balance360.models.account import Account
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.models.serial_number import SerialNumber
from balance360.schemas.invoice import InvoiceCreate
from balance360.schemas.invoice_line import InvoiceLineCreate
from balance360.schemas.transaction import TransactionCreate
from balance360.services.arca import get_access_ticket
from balance360.services.stock import get_product_stock
from balance360.services.text import digits_only
from balance360.services.wsfe import authorize_invoice as wsfe_authorize_invoice


def confirm_invoice(db: Session, invoice: Invoice):
    """Congela el comprobante como documento, y mueve la mercaderia si ya se puede.

    Confirmar dejo de exigir seriales y stock: eso pasa a ser el otro hecho, el que
    registra `fulfill_invoice`. Lo que se conserva es el tramite de todos los dias —
    cuando la mercaderia esta y los seriales ya estan cargados, confirmar sigue moviendo
    el stock en el mismo click. Cuando falta algo, el comprobante queda confirmado con
    la entrega pendiente en vez de rechazado, y esa es toda la diferencia: se puede
    autorizar, imprimir y cobrar sin tener todavia la unidad fisica.
    """
    validate_confirmation(invoice)
    invoice.confirmed = True
    db.flush()

    if fulfillment_error(db, invoice) is None:
        fulfill_invoice(db, invoice, invoice.date)

    db.flush()


def unconfirm_invoice(db: Session, invoice: Invoice):
    validate_unconfirmation(invoice)
    invoice.confirmed = False
    db.flush()


def fulfill_invoice(db: Session, invoice: Invoice, on: date) -> None:
    """Registra que las unidades se movieron: entregadas al cliente, recibidas del proveedor.

    Es lo que mueve los seriales y lo que hace que la linea cuente en el stock. `on` es
    el dia del movimiento, que no tiene por que ser el del comprobante.
    """
    if not invoice.confirmed:
        raise InvoiceFulfillmentError("El comprobante no esta confirmado")
    if invoice.fulfilled:
        raise InvoiceFulfillmentError("El movimiento ya esta registrado")

    error = fulfillment_error(db, invoice)
    if error:
        raise InvoiceFulfillmentError(error)

    _advance_serials(invoice)
    invoice.fulfilled_at = on
    db.flush()


def unfulfill_invoice(db: Session, invoice: Invoice) -> None:
    """Deshace el movimiento fisico. El comprobante sigue confirmado."""
    validate_unfulfillment(invoice)
    _rewind_serials(invoice)
    invoice.fulfilled_at = None
    db.flush()


def _serial_lines(invoice: Invoice) -> list[InvoiceLine]:
    """Las lineas cuyo producto lleva numero de serie; el resto no mueve seriales."""
    return [line for line in invoice.invoice_lines if line.product and line.product.track_serial]


def _advance_serials(invoice: Invoice) -> None:
    if not invoice.is_nc:
        for line in _serial_lines(invoice):
            if invoice.invoice_type == InvoiceType.purchase:
                for serial in line.purchased_serials:
                    serial.status = SerialStatus.available
            else:
                for serial in line.sold_serials:
                    serial.status = SerialStatus.sold
        return

    # Una NC no mueve sus propias lineas: deshace las del comprobante original. Una NC
    # cargada a mano desde ARCA no tiene original, y ahi no hay seriales que mover.
    original = invoice.related_invoice
    if original is None:
        return

    if not original.fulfilled:
        _release_commitment(original)
        return

    for line in _serial_lines(original):
        if invoice.invoice_type == InvoiceType.purchase:
            for serial in line.purchased_serials:
                serial.status = SerialStatus.returned
        else:
            for serial in line.sold_serials:
                serial.status = SerialStatus.available
                serial.sale_line_id = None


def _release_commitment(original: Invoice) -> None:
    """La NC anula un movimiento que todavia no habia ocurrido.

    Es el caso que abre facturar antes de entregar: una venta emitida —con CAE incluso—
    que se cae antes de la entrega. No hay nada que devolver, pero las unidades que esa
    venta tenia reservadas tienen que volver al stock disponible; si no, quedan fuera de
    circulacion sin ningun comprobante que lo explique.

    La compra no necesita nada aca: sus seriales serian promesas de unidades que nunca
    llegaron, y `_credit_note_error` no deja llegar hasta aca si hay alguno cargado.
    """
    for line in _serial_lines(original):
        for serial in line.sold_serials:
            serial.status = SerialStatus.available
            serial.sale_line_id = None


def _rewind_serials(invoice: Invoice) -> None:
    if not invoice.is_nc:
        for line in _serial_lines(invoice):
            if invoice.invoice_type == InvoiceType.purchase:
                for serial in line.purchased_serials:
                    serial.status = SerialStatus.pending
            else:
                for serial in line.sold_serials:
                    serial.status = SerialStatus.reserved
        return

    original = invoice.related_invoice
    if original is None or not original.fulfilled:
        return
    # La rama de venta es inalcanzable a proposito: validate_unfulfillment la rechaza
    # porque el vinculo que haria falta para restaurar los seriales ya no existe.
    # El motivo esta en PENDING.md.
    if invoice.invoice_type == InvoiceType.purchase:
        for line in _serial_lines(original):
            for serial in line.purchased_serials:
                serial.status = SerialStatus.available


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


def delete_invoice_line(db: Session, invoice_line: InvoiceLine) -> None:
    """Borra una linea de un comprobante sin confirmar y suelta sus seriales.

    La FK sale_line_id es ON DELETE SET NULL: al borrar la linea el serial pierde
    el vinculo con la venta, pero su estado no se toca solo y queda en `reserved`
    para siempre —fuera del stock disponible y sin comprobante que lo explique—.
    Mismo criterio que delete_invoice. Solo una venta reserva seriales; en una
    compra sold_serials esta vacio y el bucle no hace nada.
    """
    for serial in invoice_line.sold_serials:
        serial.status = SerialStatus.available
        serial.sale_line_id = None

    invoice_line_crud.delete(db, invoice_line)
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


def _wrong_status_message(serial: SerialNumber, required: SerialStatus) -> str:
    return f"El serial {serial.serial} {_SERIAL_STATUS_ERROR[required]}"


def validate_confirmation(invoice: Invoice) -> None:
    """Lo que hace valido al comprobante como documento.

    Nada fisico: los seriales y el stock los mira `fulfillment_error`. Un comprobante
    puede ser impecable como documento —y declarable, y cobrable— antes de que la
    mercaderia exista.
    """
    if invoice.confirmed:
        raise InvoiceConfirmationError("El comprobante ya esta confirmado")

    if not invoice.invoice_lines:
        raise InvoiceConfirmationError("El comprobante no tiene items")

    if invoice.tax_only and invoice.invoice_type == InvoiceType.sale:
        raise InvoiceConfirmationError(
            "Un comprobante no puede ser venta y solo impositivo simultaneamente"
        )

    _validate_formality(invoice)


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


def fulfillment_error(db: Session, invoice: Invoice) -> str | None:
    """Que falta para poder registrar el movimiento fisico, o None si no falta nada.

    Devuelve el motivo en vez de lanzar porque tiene dos usos con la misma pregunta
    adentro: `fulfill_invoice` lo convierte en excepcion, y `confirm_invoice` lo usa
    para decidir si puede mover el stock en el mismo acto. Tambien es lo que la lista
    de pendientes muestra en la columna "Falta".
    """
    if invoice.is_nc:
        return _credit_note_error(db, invoice)

    is_sale = invoice.invoice_type == InvoiceType.sale
    required = SerialStatus.reserved if is_sale else SerialStatus.pending

    if is_sale:
        error = _stock_error(db, invoice, invoice.entity_id)
        if error:
            return error

    for line in _serial_lines(invoice):
        product = line.product
        assert product  # _serial_lines ya filtro por producto; esto es para mypy

        serials = line.sold_serials if is_sale else line.purchased_serials
        missing = line.quantity - len(serials)
        if missing > 0:
            return f"Faltan {missing} de {line.quantity} seriales de {product.name}"
        if missing < 0:
            return f"Cantidad erronea de seriales para {product.name}"

        for serial in serials:
            if serial.product_id != line.product_id:
                return "El serial no corresponde a este producto"
            if serial.status != required:
                return _wrong_status_message(serial, required)
            if is_sale and serial.purchase_line.invoice.entity_id != invoice.entity_id:
                return "El serial no fue comprado por esta entidad"

    return None


def _credit_note_error(db: Session, invoice: Invoice) -> str | None:
    """Una NC se valida contra el comprobante original, no contra sus propias lineas."""
    original = invoice.related_invoice
    # Una NC cargada a mano desde el portal de ARCA no tiene original: no mueve nada.
    if original is None:
        return None

    if not original.fulfilled:
        # El original nunca se movio, asi que la NC no devuelve: anula. Lo unico que hay
        # que soltar es lo que habia quedado comprometido. En una compra eso serian
        # seriales `pending` de unidades que nunca llegaron, y borrarlos por nuestra
        # cuenta seria decidir solos que ese numero de serie no existio.
        if invoice.invoice_type == InvoiceType.purchase and any(
            line.purchased_serials for line in _serial_lines(original)
        ):
            return "La compra tiene seriales cargados: quitalos antes de anularla con la NC"
        return None

    if invoice.invoice_type == InvoiceType.purchase:
        # Devolver al proveedor saca unidades del deposito: tienen que estar.
        return _stock_error(db, original, invoice.entity_id) or _serials_status_error(
            original, SerialStatus.available
        )
    return _serials_status_error(original, SerialStatus.sold)


def _stock_error(db: Session, source: Invoice, entity_id: UUID) -> str | None:
    """Stock fisico suficiente para los productos de `source` que no llevan seriales.

    Los que llevan seriales no se cuentan por stock sino por serial, unidad por unidad.
    """
    for line in source.invoice_lines:
        if not line.product or line.product.track_serial:
            continue
        if get_product_stock(db, line.product.id, entity_id) < line.quantity:
            return f"Stock insuficiente de {line.product.name}"
    return None


def _serials_status_error(invoice: Invoice, required: SerialStatus) -> str | None:
    is_purchase = invoice.invoice_type == InvoiceType.purchase
    for line in _serial_lines(invoice):
        for serial in line.purchased_serials if is_purchase else line.sold_serials:
            if serial.status != required:
                return _wrong_status_message(serial, required)
    return None


def _ensure_serials_have_status(invoice: Invoice, required: SerialStatus) -> None:
    error = _serials_status_error(invoice, required)
    if error:
        raise InvoiceFulfillmentError(error)


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


def validate_unconfirmation(invoice: Invoice):
    if not invoice.confirmed:
        raise InvoiceConfirmationError("El comprobante no esta confirmado")
    if invoice.paid:
        raise InvoiceConfirmationError("El comprobante tiene pago asociado")
    if invoice.authorized:
        raise InvoiceConfirmationError("El comprobante esta autorizado CAE")
    if invoice.fulfilled:
        # Los seriales y el stock ya se movieron, y deshacer eso es la otra operacion,
        # con sus propias reglas. Des-confirmar por arriba dejaria el movimiento hecho y
        # el comprobante en borrador: stock que existe sin nada que lo respalde.
        raise InvoiceConfirmationError("Primero hay que revertir la entrega o recepcion registrada")


def validate_unfulfillment(invoice: Invoice) -> None:
    if not invoice.fulfilled:
        raise InvoiceFulfillmentError("El comprobante no tiene movimiento registrado")

    if not invoice.is_nc:
        _ensure_serials_have_status(
            invoice,
            SerialStatus.available
            if invoice.invoice_type == InvoiceType.purchase
            else SerialStatus.sold,
        )
        return

    original = invoice.related_invoice
    if original is None:
        return

    if invoice.invoice_type == InvoiceType.sale:
        # Confirmar la NC de una venta le saca el `sale_line_id` a cada serial, y esa
        # columna *es* la definicion de `sold_serials`: despues de eso no queda por
        # donde volver. Vale igual para la NC que anulo una venta sin entregar, que
        # suelta las reservas de la misma manera. El arreglo real esta en PENDING.md.
        if _serial_lines(original):
            raise InvoiceFulfillmentError(
                "No se puede revertir el movimiento de una NC de una venta con seriales"
            )
        return

    if original.fulfilled:
        _ensure_serials_have_status(original, SerialStatus.returned)


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
