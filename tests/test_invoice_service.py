import pytest
from datetime import date
from tests import factories
from balance360.services.invoice import confirm_invoice, register_payment
from balance360.services.import_rule import resolve_rule_for_classification, RuleConflictError
from balance360.exceptions import InvoiceConfirmationError
from balance360.enums import TransactionType, InvoiceType
from balance360.crud.transaction import get_all

def test_without_invoice_lines(db):
    invoice = factories.make_invoice(db)
    with pytest.raises(InvoiceConfirmationError):
        confirm_invoice(db, invoice)

def test_confirm_without_payment(db):
    invoice = factories.make_invoice(db)
    factories.make_invoice_line(db,invoice.id)
    confirm_invoice(db, invoice) 
    assert invoice.confirmed
    assert not invoice.paid

def test_confirm_with_payment(db):
    invoice = factories.make_invoice(db)
    factories.make_invoice_line(db,invoice.id)
    account = factories.make_account(db)
    confirm_invoice(db, invoice) 
    register_payment(db, invoice, account, date.today())
    assert invoice.confirmed
    assert invoice.paid
    transactions = get_all(
        db,
        account_id=account.id,
        entity_id=invoice.entity_id,
        transaction_type=TransactionType.expense if invoice.invoice_type==InvoiceType.purchase else TransactionType.income,
        )
    assert next(t for t in transactions if invoice.total == t.amount)

def test_import_rule_no_match(db):
    entity = factories.make_entity(db, "casa")
    contact = factories.make_contact(db)
    
    rule = factories.make_import_rule(
        db=db, 
        pattern="metrogas",
        transaction_type=TransactionType.expense,
        entity_id=entity.id,
        contact_id=contact.id
    )

    no_match_description = "otra cosa"
    no_match = resolve_rule_for_classification(
        db=db, 
        description=no_match_description,
        transaction_type=TransactionType.expense,
        entity_id=entity.id,
        contact_id=contact.id
    )
    
    assert no_match != None
    assert no_match != rule
    assert no_match.pattern == no_match_description

def test_import_rule_re_use(db):
    entity = factories.make_entity(db, "casa")
    contact = factories.make_contact(db)

    rule = factories.make_import_rule(
        db=db, 
        pattern="metrogas",
        transaction_type=TransactionType.expense,
        entity_id=entity.id,
        contact_id=contact.id
    )


    re_use = resolve_rule_for_classification(
        db=db,
        description="metrogas", 
        transaction_type=TransactionType.expense,
        entity_id=entity.id,
        contact_id=contact.id
    )    
    assert rule == re_use

def test_import_rule_conflict(db):
    entity = factories.make_entity(db, "casa")
    contact = factories.make_contact(db)
    category = factories.make_category(db)

    factories.make_import_rule(
        db=db, 
        pattern="metrogas",
        transaction_type=TransactionType.expense,
        entity_id=entity.id,
        contact_id=contact.id
    )

    with pytest.raises(RuleConflictError):
        resolve_rule_for_classification(
            db=db,
            description="metrogas", 
            transaction_type=TransactionType.expense,
            entity_id=entity.id,
            contact_id=contact.id,
            category_id=category.id
        )    

def test_import_rule_update(db):
    entity = factories.make_entity(db, "casa")
    contact = factories.make_contact(db)
    category = factories.make_category(db)

    rule = factories.make_import_rule(
        db=db, 
        pattern="metrogas",
        transaction_type=TransactionType.expense,
        entity_id=entity.id,
        contact_id=contact.id
    )

    resolve_rule_for_classification(
        db=db,
        description="metrogas", 
        transaction_type=TransactionType.expense,
        entity_id=entity.id,
        contact_id=contact.id,
        category_id=category.id,
        force=True
    )    

    assert rule.category_id == category.id



