from datetime import date

import pytest

from balance360.crud.transaction import get_all
from balance360.enums import InvoiceType, TransactionType
from balance360.exceptions import InvoiceConfirmationError
from balance360.services.invoice import confirm_invoice, register_payment
from tests import factories


def test_without_invoice_lines(db):
    invoice = factories.make_invoice(db)
    with pytest.raises(InvoiceConfirmationError):
        confirm_invoice(db, invoice)


def test_confirm_without_payment(db):
    invoice = factories.make_invoice(db)
    factories.make_invoice_line(db, invoice.id)
    confirm_invoice(db, invoice)
    assert invoice.confirmed
    assert not invoice.paid


def test_confirm_with_payment(db):
    invoice = factories.make_invoice(db)
    factories.make_invoice_line(db, invoice.id)
    account = factories.make_account(db)
    confirm_invoice(db, invoice)
    register_payment(db, invoice, account, date.today())
    assert invoice.confirmed
    assert invoice.paid
    transactions = get_all(
        db,
        account_id=account.id,
        entity_id=invoice.entity_id,
        transaction_type=TransactionType.expense
        if invoice.invoice_type == InvoiceType.purchase
        else TransactionType.income,
    )
    assert next(t for t in transactions if invoice.total == t.amount)
