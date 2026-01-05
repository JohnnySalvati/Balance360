from datetime import date
from django.db.models import Sum, DecimalField
from django.db.models.functions import TruncMonth

from apps.finance.models import Transaction, Category
from apps.finance.services.entities import get_consolidated_entities
from apps.finance.models import PeriodClose

from decimal import Decimal
from calendar import monthrange

def base_queryset():
    transfer_category = Category.objects.get(name="Transferencias")

    return Transaction.objects.exclude(category=transfer_category)


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
    resultado = Decimal("0")

    qs = base_queryset().filter(
        entity__in=entities,
        date__date__gte=start,
        date__date__lte=end,
    )

    for entity in entities:
        close = PeriodClose.objects.filter(
            entity=entity,
            year=year,
            month=month,
        ).first()

        if close:
            ingresos += close.ingresos
            egresos += close.egresos
            resultado += close.resultado
        else:
            ingresos = (
                qs.filter(amount__gt=0)
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )

            egresos = (
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
        qs = qs.filter(date__date__gte=start, date__date__lte=end)

    return qs.aggregate(
        total=Sum("amount"))["total"] or Decimal("0")


def account_balance(account, entity=None, start=None, end=None):
    qs = base_queryset().filter(account=account)
    entities = get_consolidated_entities(entity) if entity else None

    if entities:
        qs = qs.filter(entity__in=entities)

    if start and end:
        qs = qs.filter(date__date__gte=start, date__date__lte=end)

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
