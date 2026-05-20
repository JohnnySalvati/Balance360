import uuid
from datetime import date
from sqlalchemy.orm import Session
from balance360.crud import transaction as transaction_crud
from balance360.models.invoice import Invoice
from balance360.models.account import Account
from balance360.schemas.transaction import TransactionCreate
from balance360.enums import VoucherStatus, TransactionType, InvoiceType

class InvoiceDeleteError(Exception):
    pass

class InvoiceConfirmError(Exception):
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
            is_manual=False,
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
