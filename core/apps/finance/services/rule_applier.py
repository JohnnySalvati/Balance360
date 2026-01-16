from django.db.models import Q

from apps.finance.models.transaction import Transaction
from apps.finance.services.classification_engine import evaluate_rule


def apply_rule(rule):
    qs = (
        Transaction.objects
        .filter(description__icontains=rule.pattern)
        .filter(
            Q(classification_source__isnull=True) |
            Q(classification_source="rule")
        )
        .distinct()
    )

    updated = 0

    for tx in qs.iterator():
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
        updated += 1

    return updated
