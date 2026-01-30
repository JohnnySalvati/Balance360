from django.db.models import Q, Count
from apps.finance.models.transaction import Transaction


def classification_summary():
    total = Transaction.objects.count()

    by_source = (
        Transaction.objects
        .values("classification_source")
        .annotate(count=Count("id"))
    )

    unresolved = Transaction.objects.filter(
        Q(entity__isnull=True) | Q(category__isnull=True)
    ).count()

    return {
        "total": total,
        "unresolved": unresolved,
        "resolved": total - unresolved,
        "by_source": {
            row["classification_source"] or "unclassified": row["count"]
            for row in by_source
        },
    }
