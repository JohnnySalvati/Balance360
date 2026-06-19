import pytest
from tests import factories
from balance360.services.import_rule import resolve_rule_for_classification
from balance360.exceptions import RuleConflictError
from balance360.enums import TransactionType
from balance360.services.import_rule import Classification

def test_import_rule_no_match(db):
    entity = factories.make_entity(db, "casa")
    contact = factories.make_contact(db)
    classification = Classification(
        entity_id=entity.id,
        contact_id=contact.id
    )
        
    rule = factories.make_import_rule(
        db=db, 
        pattern="metrogas",
        classification=classification,
        transaction_type=TransactionType.expense,
    )

    classification = Classification(
        entity_id=entity.id,
        contact_id=contact.id
    )

    no_match_description = "otra cosa"
    no_match = resolve_rule_for_classification(
        db=db, 
        description=no_match_description,
        transaction_type=TransactionType.expense,
        classification=classification
    )
    
    assert no_match is not None
    assert no_match != rule
    assert no_match.pattern == no_match_description

def test_import_rule_re_use(db):
    entity = factories.make_entity(db, "casa")
    contact = factories.make_contact(db)
    classification = Classification(
        entity_id=entity.id,
        contact_id=contact.id
    )

    rule = factories.make_import_rule(
        db=db, 
        pattern="metrogas",
        transaction_type=TransactionType.expense,
        classification=classification
    )


    re_use = resolve_rule_for_classification(
        db=db,
        description="metrogas", 
        transaction_type=TransactionType.expense,
        classification=classification
    )    
    assert rule == re_use

def test_import_rule_conflict(db):
    entity = factories.make_entity(db, "casa")
    contact = factories.make_contact(db)
    category = factories.make_category(db)
    
    classification = Classification(
        entity_id=entity.id,
        contact_id=contact.id
    )

    factories.make_import_rule(
        db=db, 
        pattern="metrogas",
        transaction_type=TransactionType.expense,
        classification=classification
    )
    classification = Classification(
        entity_id=entity.id,
        contact_id=contact.id,
        category_id=category.id
    )

    with pytest.raises(RuleConflictError):
        resolve_rule_for_classification(
            db=db,
            description="metrogas", 
            transaction_type=TransactionType.expense,
            classification=classification
        )    

def test_import_rule_update(db):
    entity = factories.make_entity(db, "casa")
    contact = factories.make_contact(db)
    category = factories.make_category(db)

    classification = Classification(
        entity_id=entity.id,
        contact_id=contact.id
    )

    rule = factories.make_import_rule(
        db=db, 
        pattern="metrogas",
        transaction_type=TransactionType.expense,
        classification=classification
    )

    classification = Classification(
        entity_id=entity.id,
        contact_id=contact.id,
        category_id=category.id
    )

    resolve_rule_for_classification(
        db=db,
        description="metrogas", 
        transaction_type=TransactionType.expense,
        classification=classification,
        force=True
    )    

    assert rule.category_id == category.id



