from datetime import date

from apps.finance.models.transaction import Account, Transaction
from apps.finance.models.classification_rule import ClassificationRule
from apps.finance.models.category import Category
from apps.finance.models.entity import EconomicEntity
from apps.finance.services.classifier import classify_transaction
from apps.accounts.models import User

def user_entity(name="test"):
    user = User.objects.create(username=name)
    return EconomicEntity.objects.get(
        content_type__model="user",
        object_id=user.id, # type: ignore
    )

def test_rule_applies_to_unclassified_transaction(db):
    entity = user_entity("insoft")
    category = Category.objects.create(name="Gastos",
                                       is_income=False)
    account = Account.objects.create(
        name="Cuenta Test",
    )


    tx = Transaction.objects.create(
        account=account,
        description="Pago VISA supermercado",
        amount=-100,
        date=date(2025, 1, 1),
    )

    rule = ClassificationRule.objects.create(
        pattern="visa",
        entity=entity,
        category=category,
        confidence=100,
        is_active=True,
    )

    changed = classify_transaction(tx)

    tx.refresh_from_db()

    assert changed is True
    assert tx.entity == entity
    assert tx.category == category
    assert tx.classification_source == "rule"

def test_manual_classification_is_not_overwritten(db):
    entity_manual = user_entity("Casa")
    category_manual = Category.objects.create(name="Gastos",
                                              is_income=False)
    entity_rule = user_entity("Insoft")
    category_rule = Category.objects.create(name="Ingresos",
                                            is_income=True)
    account = Account.objects.create(
        name="Cuenta Test",
    )

    tx = Transaction.objects.create(
        account=account,
        description="Pago VISA supermercado",
        amount=-100,
        entity=entity_manual,
        category=category_manual,
        classification_source="manual",
        date=date(2025, 1, 1),
    )

    ClassificationRule.objects.create(
        pattern="visa",
        entity=entity_rule,
        category=category_rule,
        confidence=100,
        is_active=True,
    )

    changed = classify_transaction(tx)

    tx.refresh_from_db()

    assert changed is False
    assert tx.entity == entity_manual
    assert tx.category == category_manual

def test_rule_completes_missing_category(db):
    entity = user_entity("insoft")
    category = Category.objects.create(name="Gastos",
                                       is_income=False)
    account = Account.objects.create(
        name="Cuenta Test",
    )

    tx = Transaction.objects.create(
        account=account,
        description="Pago VISA supermercado",
        amount=-100,
        entity=entity,
        date=date(2025, 1, 1),
        classification_source="rule",
    )

    ClassificationRule.objects.create(
        pattern="visa",
        category=category,
        confidence=100,
        is_active=True,
    )

    changed = classify_transaction(tx)

    tx.refresh_from_db()

    assert changed is True
    assert tx.entity == entity
    assert tx.category == category

def test_inactive_rule_does_not_apply(db):
    account = Account.objects.create(
        name="Cuenta Test",
    )
    tx = Transaction.objects.create(
        account=account,
        description="Pago VISA",
        amount=-100,
        date=date(2025, 1, 1),
    )
    category = Category.objects.create(
        name="Gastos",
        is_income=False,
    )

    ClassificationRule.objects.create(
        category = category,
        pattern="visa",
        confidence=100,
        is_active=False,
    )

    changed = classify_transaction(tx)

    tx.refresh_from_db()

    assert changed is False
    assert tx.entity is None
    assert tx.category is None
