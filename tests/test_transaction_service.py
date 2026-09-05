from datetime import date
from decimal import Decimal

from balance360.crud import transaction as transaction_crud
from balance360.crud.transaction import get_all, get_by_id
from balance360.enums import TransactionType
from balance360.schemas.transaction import TransactionCreate
from balance360.services.invoice import confirm_invoice, register_payment
from balance360.services.transaction import delete
from tests import factories


def test_delete_payment_transaction_reverts_invoice_paid(db):
    invoice = factories.make_invoice(db, formal=False)
    factories.make_invoice_line(db, invoice.id)
    account = factories.make_account(db)
    confirm_invoice(db, invoice)
    register_payment(db, invoice, account, date.today())
    assert invoice.paid

    payment = next(t for t in get_all(db) if t.invoice_id == invoice.id)
    delete(db, payment)

    assert not invoice.paid
    assert get_by_id(db, payment.id) is None


def test_delete_plain_transaction_leaves_invoices_alone(db):
    account = factories.make_account(db)
    transaction = transaction_crud.create(
        db,
        TransactionCreate(
            date=date.today(),
            description="Gasto suelto",
            amount=Decimal("100"),
            type=TransactionType.expense,
            account_id=account.id,
            is_manual=True,
        ),
    )

    delete(db, transaction)

    assert get_by_id(db, transaction.id) is None
