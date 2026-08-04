import dataclasses
import datetime
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from balance360.enums import (
    AccountType,
    CondicionIva,
    ContactType,
    DocType,
    InvoiceType,
    IvaAliquot,
    TransactionType,
    VoucherType,
)
from balance360.models.account import Account
from balance360.models.category import Category
from balance360.models.contact import Contact
from balance360.models.currency import Currency
from balance360.models.entity import Entity
from balance360.models.exchange_rate import ExchangeRate
from balance360.models.fiscal_identity import FiscalIdentity
from balance360.models.import_rule import ImportRule
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.services.import_rule import Classification


def make_entity(db: Session, name="Test"):
    entity = Entity(id=uuid.uuid4(), name=name)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def make_fiscal_identity(
    db: Session, name="Test", condicion_iva=CondicionIva.INSCRIPTO, tax_id=None
):
    fiscal_identity = FiscalIdentity(
        id=uuid.uuid4(),
        name=name,
        condicion_iva=condicion_iva,
        tax_id=tax_id or str(uuid.uuid4().int)[:11],
    )
    db.add(fiscal_identity)
    db.commit()
    db.refresh(fiscal_identity)
    return fiscal_identity


def make_contact(
    db: Session,
    name="Test",
    tax_id="11111111111",
    contact_type=ContactType.both,
    email="test@testing.com.ar",
    condicion_iva=CondicionIva.INSCRIPTO,
    doc_type=DocType.CUIT,
):
    contact = Contact(
        id=uuid.uuid4(),
        name=name,
        tax_id=tax_id,
        contact_type=contact_type,
        email=email,
        condicion_iva=condicion_iva,
        doc_type=doc_type,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def make_currency(
    db: Session,
    code="ARS",
    name="Pesos",
    is_bond=False,
):
    currency = Currency(id=uuid.uuid4(), code=code, name=name, is_bond=is_bond)
    db.add(currency)
    db.commit()
    db.refresh(currency)
    return currency


def make_account(db: Session, name="Test", type=AccountType.bank, currency_id=None):
    account = Account(
        id=uuid.uuid4(), name=name, type=type, currency_id=currency_id or make_currency(db).id
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def make_category(db: Session, name: str = "Compras", parent_id: uuid.UUID | None = None):
    category = Category(name=name, parent_id=parent_id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def make_invoice(
    db: Session,
    invoice_type=None,
    fiscal_identity_id=None,
    entity_id=None,
    contact_id=None,
    category_id=None,
    date=None,
    formal=True,
    pos=1,
    number=45,
    voucher_type=None,
):
    entity_id = entity_id or make_entity(db).id
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_type=invoice_type or InvoiceType.purchase,
        entity_id=entity_id,
        fiscal_identity_id=fiscal_identity_id or make_fiscal_identity(db).id,
        contact_id=contact_id or make_contact(db).id,
        category_id=category_id,
        date=date if date else datetime.date.today(),
        formal=formal,
        pos=pos,
        number=number,
        voucher_type=voucher_type if voucher_type else VoucherType.A,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def make_invoice_line(
    db: Session,
    invoice_id=None,
    product_id=None,
    description="Test ",
    quantity=1,
    unit_price=Decimal("125.5"),
    iva_aliquot=IvaAliquot.exempt,
):
    invoice_line = InvoiceLine(
        id=uuid.uuid4(),
        invoice_id=invoice_id or make_invoice(db).id,
        product_id=product_id,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        iva_aliquot=iva_aliquot,
    )
    db.add(invoice_line)
    db.commit()
    db.refresh(invoice_line)
    return invoice_line


def make_import_rule(
    db: Session,
    pattern: str,
    classification: Classification,
    transaction_type: TransactionType = TransactionType.expense,
):
    import_rule = ImportRule(
        id=uuid.uuid4(),
        pattern=pattern,
        **dataclasses.asdict(classification),
        transaction_type=transaction_type,
    )
    db.add(import_rule)
    db.commit()
    db.refresh(import_rule)
    return import_rule


def make_exchange_rate(
    db: Session,
    currency_id: uuid.UUID | None = None,
    date: datetime.date | None = None,
    rate: Decimal | None = Decimal(0),
):
    date = date if date else datetime.date.today()
    exchange_rate = ExchangeRate(
        id=uuid.uuid4(), currency_id=currency_id or make_currency(db).id, date=date, rate=rate
    )
    db.add(exchange_rate)
    db.commit()
    db.refresh(exchange_rate)
    return exchange_rate
