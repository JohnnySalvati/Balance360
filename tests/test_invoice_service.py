import pytest
from tests import factories
from balance360.services.invoice import confirm_invoice, InvoiceConfirmError
from balance360.enums import VoucherStatus, TransactionType, InvoiceType
from balance360.crud.transaction import get_all

def test_without_invoice_lines(db):
    with pytest.raises(InvoiceConfirmError):
        invoice = factories.make_invoice(db)
        confirm_invoice(db, invoice)

def test_confirm_without_account(db):
    invoice = factories.make_invoice(db)
    factories.make_invoice_line(db,invoice.id)
    confirm_invoice(db, invoice) 
    assert invoice.status == VoucherStatus.pending

def test_confirm_with_account(db):
    invoice = factories.make_invoice(db)
    factories.make_invoice_line(db,invoice.id)
    account = factories.make_account(db)
    confirm_invoice(db, invoice, account=account) 
    assert invoice.status == VoucherStatus.paid
    transactions = get_all(
        db,
        account_id=account.id,
        entity_id=invoice.entity_id,
        transaction_type=TransactionType.expense if invoice.invoice_type==InvoiceType.purchase else TransactionType.income,
        )
    next(t for t in transactions if invoice.total == t.amount)

        
