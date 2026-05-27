import uuid
import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from balance360.models.entity import Entity
from balance360.models.contact import Contact
from balance360.models.account import Account
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.models.currency import Currency
from balance360.enums import ContactType, AccountType, InvoiceType

def make_entity(db: Session, name="Test"):
    entity = Entity(id=uuid.uuid4(), name= name)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity

def make_contact(
        db: Session,
        name="Test",
        tax_id="11-11111111-1",
        contact_type=ContactType.both,
        email= "test@testing.com.ar"
        ):
    contact = Contact(
        id=uuid.uuid4(),
        name=name,
        tax_id=tax_id,
        contact_type=contact_type,
        email=email)
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
    currency = Currency(
        id=uuid.uuid4(),
        code=code,
        name=name,
        is_bond=is_bond
    )
    db.add(currency)
    db.commit()
    db.refresh(currency)
    return currency

def make_account(
    db: Session,
    name="Test",
    type=AccountType.bank,
    currency_id=None
):
    account = Account(
        id=uuid.uuid4(),
        name=name,
        type=type,
        currency_id=currency_id or make_currency(db).id
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account

def make_invoice(
        db: Session,
        invoice_type=InvoiceType.purchase,
        entity_id=None,
        contact_id=None,
        category_id=None,
        date=None
):
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_type=invoice_type,
        entity_id=entity_id or make_entity(db).id,
        contact_id=contact_id or make_contact(db).id,
        category_id=category_id,
        date=date if date else datetime.date.today()
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
        unit_price=Decimal("125.5")
):
    invoice_line = InvoiceLine(
        id=uuid.uuid4(),
        invoice_id=invoice_id or make_invoice(db).id,
        product_id=product_id,
        description=description,
        quantity=quantity,
        unit_price=unit_price
    )
    db.add(invoice_line)
    db.commit()
    db.refresh(invoice_line)
    return invoice_line
