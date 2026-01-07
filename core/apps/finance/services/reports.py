from django.db.models import Sum, DecimalField
from django.db.models.functions import TruncMonth

from apps.finance.models import Transaction
from apps.finance.services.entities import get_consolidated_entities
from apps.finance.models import PeriodClose

from decimal import Decimal
from calendar import monthrange
from datetime import date
def base_queryset():
    return Transaction.objects.exclude(category__is_transfer_root=True)

def monthly_balance(entity):
    entities = get_consolidated_entities(entity)
    qs = base_queryset().filter(entity__in=entities)

    return (
        qs.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(
            total=Sum("amount", output_field=DecimalField())
            )
        
        .order_by("month")
    )

def period_result(entity, year, month):
    entities = get_consolidated_entities(entity)
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    ingresos = Decimal("0")
    egresos = Decimal("0")
    
    open_entities = []

    qs = base_queryset().filter(
        entity__in=entities,
        date__gte=start,
        date__lte=end,
    )

    for e in entities:
        close = PeriodClose.objects.filter(
            entity=e,
            year=year,
            month=month,
        ).first()

        if close:
            ingresos += close.ingresos
            egresos += close.egresos
        else:
            open_entities.append(e)

    if open_entities:
        qs = base_queryset().filter(
            entity__in=open_entities,
            date__gte=start,
            date__lte=end,
        )

        ingresos += (
            qs.filter(amount__gt=0)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        egresos += (
            qs.filter(amount__lt=0)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

    return {
        "ingresos": ingresos,
        "egresos": egresos,
        "resultado": ingresos + egresos,
    }

def get_descendants(category):
    descendants = []

    def recurse(cat):
        for child in cat.children.all():
            descendants.append(child)
            recurse(child)

    recurse(category)
    return descendants

def total_by_category(category, entity=None, start=None, end=None):
    categories = [category] + get_descendants(category)
    entities = get_consolidated_entities(entity) if entity else None
    qs = base_queryset().filter(category__in=categories)

    if entities:
        qs = qs.filter(entity__in=entities)

    if start and end:
        qs = qs.filter(date__gte=start, date__lte=end)

    return qs.aggregate(
        total=Sum("amount"))["total"] or Decimal("0")


def account_balance(account, entity=None, start=None, end=None):
    qs = base_queryset().filter(account=account)
    entities = get_consolidated_entities(entity) if entity else None

    if entities:
        qs = qs.filter(entity__in=entities)

    if start and end:
        qs = qs.filter(date__gte=start, date__lte=end)

    return qs.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")
    
def consolidated_balance(entities):
    result = {}

    for entity in entities:
        result[entity.name] = (
            base_queryset()
            .filter(entity=entity)
            .aggregate(
                total=Sum("amount")
            )["total"] or Decimal("0")
        )

    result["TOTAL"] = sum(result.values())
    return result
