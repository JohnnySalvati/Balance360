from django.db.models import Count
from apps.finance.models.classification_rule import ClassificationRule
from apps.finance.models.transaction import Transaction


def rule_effectiveness():
    data = []

    for rule in ClassificationRule.objects.all():
        applied = Transaction.objects.filter(
            applied_rule=rule
        ).count()

        data.append({
            "rule_id": rule.id, # type: ignore
            "pattern": rule.pattern,
            "confidence": rule.confidence,
            "is_active": rule.is_active,
            "applied_count": applied,
        })

    return sorted(
        data,
        key=lambda r: r["applied_count"],
        reverse=True,
    )
