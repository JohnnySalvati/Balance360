# apps/finance/services/classification/health.py

from django.db.models import Q
from apps.finance.models.transaction import Transaction


def get_classification_health():
    """
    Devuelve métricas de estado de clasificación de transacciones.
    Pensado para ser reutilizado desde admin, API o CLI.
    """

    total = Transaction.objects.count()

    unclassified = Transaction.objects.filter(
        entity__isnull=True,
        category__isnull=True,
    ).count()

    rule_classified = Transaction.objects.filter(
        classification_source="rule"
    ).count()

    manual_classified = Transaction.objects.filter(
        classification_source="manual"
    ).count()

    partial = Transaction.objects.filter(
        Q(entity__isnull=True, category__isnull=False) |
        Q(entity__isnull=False, category__isnull=True)
    ).count()

    return {
        "total": total,
        "unclassified": unclassified,
        "rule": rule_classified,
        "manual": manual_classified,
        "partial": partial,
        "all_classified": unclassified == 0,
    }
