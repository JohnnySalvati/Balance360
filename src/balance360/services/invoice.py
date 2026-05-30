from datetime import date
from sqlalchemy.orm import Session
from balance360.crud import transaction as transaction_crud
from balance360.models.invoice import Invoice
from balance360.models.account import Account
from balance360.schemas.transaction import TransactionCreate
from balance360.enums import TransactionType, InvoiceType
from balance360.dtos.invoice_request import InvoiceRequest, VoucherData, VoucherInfo, IvaDetail, Tribute
from balance360.dtos.auth import Auth
from balance360.services.arca import get_access_ticket
from balance360.services.wsfe import authorize_invoice as wsfe_authorize_invoice

class InvoiceDeleteError(Exception):
    pass
class InvoiceConfirmError(Exception):
    pass
class InvoiceRegisterPaymentError(Exception):
    pass

def confirm_invoice(db: Session, invoice: Invoice, payment_date: date|None = None, account: Account|None = None):
    invoice.validate_confirmation()
    invoice.confirmed = True
    db.flush()
    if account:
        register_payment(db, invoice, account, payment_date or date.today())

def register_payment(db: Session, invoice: Invoice, account: Account, payment_date: date):
    
    invoice.validate_payment()
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
    invoice.validate_delete()
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
    invoice.validate_authorization()
    
    invoice_request = _build_invoice_request(invoice)
    
    result = wsfe_authorize_invoice(invoice_request)

    invoice.cae = result.cae
    invoice.cae_expiry = result.expiration
    invoice.number = result.number
    invoice.authorized = True
    db.flush()

