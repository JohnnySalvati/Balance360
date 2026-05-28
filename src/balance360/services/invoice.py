import uuid
from datetime import date
from sqlalchemy.orm import Session
from balance360.crud import transaction as transaction_crud
from balance360.models.invoice import Invoice
from balance360.models.account import Account
from balance360.schemas.transaction import TransactionCreate
from balance360.enums import VoucherStatus, TransactionType, InvoiceType, DocType
from balance360.dtos.invoice_request import InvoiceRequest, VoucherData, VoucherInfo, IvaDetail, Tribute
from balance360.dtos.auth import Auth
from balance360.services.arca import get_access_ticket
from balance360.services.wsfe import authorize_invoice as wsfe_authorize_invoice

class InvoiceDeleteError(Exception):
    pass
class InvoiceConfirmError(Exception):
    pass
class InvoiceAuthorizationError(Exception):
    pass

def confirm_invoice(db: Session, invoice: Invoice, account: Account|None = None, payment_date: date|None=None):
    if not invoice.invoice_lines:
        raise InvoiceConfirmError("No se puede confirmar un comprobante sin items")
    if account:
        ref = f"{invoice.pos}-{invoice.number}" if invoice.formal else "informal"
        if invoice.invoice_type == InvoiceType.purchase:
            transaction_type = TransactionType.expense
            description = f"Compra {ref} {invoice.contact.name}"
        else:
            transaction_type = TransactionType.income
            description = f"Venta {ref} {invoice.contact.name}"
        data = TransactionCreate(
            date=payment_date or date.today(),
            description=description,
            amount=invoice.total,
            type=transaction_type,
            account_id=account.id,
            entity_id=invoice.entity_id,
            contact_id=invoice.contact_id,
            category_id=invoice.category_id,
            invoice_id=invoice.id,
            is_manual=True,
            is_transfer=False
        )
        transaction_crud.create(db, data)
        status = VoucherStatus.paid
    else:
        status = VoucherStatus.pending
    invoice.status = status
    db.commit()

def delete_invoice(db: Session, invoice: Invoice):
    if invoice.status == VoucherStatus.draft:
        db.delete(invoice)
        db.commit()
    else:
        raise InvoiceDeleteError("No se puede eliminar un comprobante que ya ha sido confirmado")

def authorize_invoice(db: Session, invoice: Invoice):
    if invoice.status != VoucherStatus.pending:
        raise InvoiceAuthorizationError(f"No se puede autorizar un comprobante cuyo status es {invoice.status}")
    
    ticket = get_access_ticket("wsfe")
    token = ticket["token"]
    sign = ticket["sign"]
    if not invoice.entity.tax_id:
        raise InvoiceAuthorizationError("La entidad no posee CUIT")
    auth = Auth(
        cuit=invoice.entity.tax_id,
        token=token,
        sign=sign
        )
    
    if not invoice.pos or not invoice.voucher_type:
        raise InvoiceAuthorizationError("El tipo y punto de venta del comprobante son obligatorios")
    voucher_info = VoucherInfo(
        pos=invoice.pos,
        voucher_type=invoice.voucher_type
        )
    
    if invoice.contact.doc_type != DocType.FINAL and not invoice.contact.tax_id:
        raise InvoiceAuthorizationError("Se necesita numero de CUIT del cliente")

    iva_detail = [IvaDetail(
        id=item.aliquot.arca_code,
        base_imp=item.net_amount,
        amount=item.iva_amount
    ) for item in invoice.iva_breakdown] 

    tributes = [Tribute(
        id=tribute.tribute_type,
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

    result = wsfe_authorize_invoice(invoice_request)

    invoice.cae = result.cae
    invoice.cae_expiry = date.fromisoformat(result.expiration)
    invoice.number = result.number
    invoice.status = VoucherStatus.authorized
    db.commit()

