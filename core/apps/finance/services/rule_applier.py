from django.db.models import Q

from apps.finance.models.transaction import Transaction
from apps.finance.services.classifier import classify_transaction

def apply_rule(rule) -> int:
    if not rule.is_active:
        return 0

    qs = (
        Transaction.objects
        .filter(description__icontains=rule.pattern)
        .filter(
            Q(classification_source__isnull=True) |
            Q(classification_source="rule")
        )
    )

    updated = 0
    rules = [rule]  # 👈 clave

    for tx in qs.iterator(chunk_size=500):
        if classify_transaction(tx, rules=rules):
            updated += 1

    return updated
