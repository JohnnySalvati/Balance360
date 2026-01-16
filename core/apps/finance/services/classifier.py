from apps.finance.models.classification_rule import ClassificationRule
from apps.finance.services.classification_engine import evaluate_rule


def classify_transaction(tx):
    rules = (
        ClassificationRule.objects
        .filter(is_active=True)
        .order_by("-confidence")
    )

    for rule in rules:
        delta = evaluate_rule(tx, rule)
        if not delta:
            continue

        tx.entity = delta.entity
        tx.category = delta.category
        tx.classification_source = "rule"

        tx.save(update_fields=[
            "entity",
            "category",
            "classification_source",
        ])

        return True

    return False
