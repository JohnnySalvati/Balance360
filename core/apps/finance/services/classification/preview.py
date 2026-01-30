from django.db.models import Q

from apps.finance.models.transaction import Transaction
from core.apps.finance.services.classification.engine import evaluate_rule


def preview_rule_impact(rule):
    qs = (
        Transaction.objects
        .filter(description__icontains=rule.pattern)
        .filter(
            Q(classification_source__isnull=True) |
            Q(classification_source="rule")
        )
        .distinct()
    )

    total = qs.count()
    would_change = 0
    samples = []

    for tx in qs[:100]:
        delta = evaluate_rule(tx, rule)
        if not delta:
            continue

        would_change += 1
        samples.append({
            "id": tx.id, # type: ignore
            "description": tx.description,
            "before": {
                "entity": tx.entity,
                "category": tx.category,
            },
            "after": {
                "entity": delta.entity,
                "category": delta.category,
            },
        })

    return {
        "matched": total,
        "would_change": would_change,
        "samples": samples[:10],
    }
