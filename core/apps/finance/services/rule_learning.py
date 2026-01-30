# apps/finance/services/rule_learning.py

from django.db import transaction

from apps.finance.models.classification_rule import ClassificationRule
from core.apps.finance.services.classification.patterns import normalize_pattern

CONFIDENCE_INC = 10
CONFIDENCE_DEC = 20
CONFIDENCE_MIN = 0
CONFIDENCE_MAX = 1000


def reinforce_rule_from_transaction(tx):
    """
    Aprendizaje explícito:
    El humano clasificó una transacción y decide aprender la regla.
    """
    if not tx.entity and not tx.category:
        return None

    pattern = normalize_pattern(tx.description)
    if not pattern:
        return None

    with transaction.atomic():
        rule, created = ClassificationRule.objects.get_or_create(
            pattern=pattern,
            entity=tx.entity,
            category=tx.category,
            defaults={"confidence": CONFIDENCE_INC},
        )

        if not created:
            rule.confidence = min(
                rule.confidence + CONFIDENCE_INC,
                CONFIDENCE_MAX,
            )
            rule.save(update_fields=["confidence"])

    return rule


def penalize_rule(rule: ClassificationRule):
    """
    Penaliza una regla cuando el humano la contradice.
    """
    if not rule:
        return

    rule.confidence = max(
        rule.confidence - CONFIDENCE_DEC,
        CONFIDENCE_MIN,
    )
    rule.save(update_fields=["confidence"])
