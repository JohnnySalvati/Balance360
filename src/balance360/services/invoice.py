from datetime import date
from sqlalchemy.orm import Session
from balance360.crud import transaction as transaction_crud
from balance360.models.invoice import Invoice
from balance360.models.account import Account
from balance360.schemas.transaction import TransactionCreate
from balance360.enums import TransactionType, InvoiceType, SerialStatus, DocType
from balance360.dtos.invoice_request import InvoiceRequest, VoucherData, VoucherInfo, IvaDetail, Tribute
from balance360.dtos.auth import Auth
from balance360.services.arca import get_access_ticket
from balance360.services.wsfe import authorize_invoice as wsfe_authorize_invoice
from balance360.services.stock import get_product_stock
from balance360.exceptions import InvoiceAuthorizationError, InvoiceConfirmationError, InvoiceDeleteError, InvoicePaymentError


def confirm_invoice(db: Session, invoice: Invoice):
    validate_confirmation(db, invoice)
    invoice.confirmed = True

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
        description=f"{'Compra' if invoice.invoice_type == InvoiceType.purchase else 'Venta'} {ref} {invoice.contact.name}",
        amount=invoice.total,
        type=TransactionType.expense if invoice.invoice_type == InvoiceType.purchase else TransactionType.income,
        account_id=account.id,
        entity_id=invoice.entity_id,
        contact_id=invoice.contact_id,
        category_id=invoice.category_id,
        invoice_id=invoice.id,
        is_manual=True,
        is_transfer=False
    )
    transaction_crud.create(db, data)
    invoice.paid = True
    db.flush()
    
def delete_invoice(db: Session, invoice: Invoice):
    validate_delete(invoice)
    db.delete(invoice)

def _build_invoice_request(invoice: Invoice) -> InvoiceRequest:
    ticket = get_access_ticket("wsfe")
    token = ticket["token"]
    sign = ticket["sign"]

    assert invoice.entity.tax_id
    assert invoice.pos
    assert invoice.voucher_type

    auth = Auth(
        cuit= invoice.entity.tax_id,
        token=token,
        sign=sign
        )
    
    voucher_info = VoucherInfo(
        pos=invoice.pos,
        voucher_type=invoice.voucher_type
        )
    
    
    iva_detail = [IvaDetail(
        id=item.aliquot.arca_code,
        base_imp=item.net_amount,
        amount=item.iva_amount
    ) for item in invoice.iva_breakdown] 

    tributes = [Tribute(
        id=tribute.tribute_type.value,
        description=tribute.description,
        base_imp=tribute.base_amount,
        aliquot=tribute.rate,
        amount=tribute.amount
    ) for tribute in invoice.invoice_tributes]

    voucher_data = VoucherData(
        date=invoice.date,
        receiver_condicion_iva=invoice.contact.condicion_iva,
        receiver_doc_type=invoice.contact.doc_type,
        receiver_doc_number=invoice.contact.tax_id or "0",
        iva_detail=iva_detail,
        tributes= tributes,
        total=invoice.total
    )

    invoice_request = InvoiceRequest(
        auth=auth,
        voucher_info=voucher_info,
        voucher_data=voucher_data
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
        if not invoice.entity.tax_id:
            raise InvoiceAuthorizationError("La entidad no posee CUIT")
    
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

def validate_confirmation(db: Session, invoice: Invoice):
    if invoice.confirmed:
        raise InvoiceConfirmationError("El comprobante ya esta confirmado")
    if not invoice.invoice_lines:
        raise InvoiceConfirmationError("El comprobante no tiene items")
    
    for invoice_line in invoice.invoice_lines:
        if not invoice_line.product:
            continue

        if invoice.invoice_type == InvoiceType.sale:
            if not invoice_line.product.track_serial:
                stock = get_product_stock(db, invoice_line.product.id, invoice.entity_id)
                if stock < invoice_line.quantity:
                    raise InvoiceConfirmationError("Stock insuficiente")
                continue
            if invoice_line.quantity != len(invoice_line.sold_serials):
                raise InvoiceConfirmationError("Cantidad erronea de seriales")
            for serial in invoice_line.sold_serials:
                if serial.product_id != invoice_line.product_id:
                    raise InvoiceConfirmationError("El serial no corresponde a este producto")
                if serial.status != SerialStatus.reserved:
                    raise InvoiceConfirmationError("El serial no esta reservado")
                if serial.purchase_line.invoice.entity_id != invoice.entity_id:
                    raise InvoiceConfirmationError("El serial no fue comprado por esta entidad")
        else:
            if not invoice_line.product.track_serial:
                continue
            if invoice_line.quantity != len(invoice_line.purchased_serials):
                raise InvoiceConfirmationError("Cantidad erronea de seriales")
            for serial in invoice_line.purchased_serials:
                if serial.product_id != invoice_line.product_id:
                    raise InvoiceConfirmationError("El serial no corresponde a este producto")
                if serial.status != SerialStatus.pending:
                    raise InvoiceConfirmationError("El serial no esta pendiente")
            

def validate_payment(invoice: Invoice):
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

    if invoice.invoice_type == InvoiceType.purchase:
        for invoice_line in invoice.invoice_lines:
            if invoice_line.product and invoice_line.product.track_serial:
                for serial in invoice_line.purchased_serials:
                    if serial.status != SerialStatus.available:
                        raise InvoiceConfirmationError(f"El serial {serial} ha sido vendido o reservado")
            
