from django.db.models import Sum, Case, When, F, DecimalField
from apps.finance.models import Transaction, Category
from django.db.models.functions import TruncMonth


def base_queryset():
    transfer_category = Category.objects.get(name="Transferencia interna")

    return Transaction.objects.exclude(category=transfer_category)


def monthly_balance(entity):
    qs = base_queryset().filter(entity=entity)

    return (
        qs.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(
            total=Sum(
                Case(
                    When(direction=Transaction.IN, then=F("amount")),
                    When(direction=Transaction.OUT, then=-F("amount")),
                    output_field=DecimalField()
                )
            )
        )
        .order_by("month")
    )

def period_result(entity, start, end):
    qs = base_queryset().filter(
        entity=entity,
        date__date__gte=start,
        date__date__lte=end,
    )

    ingresos = qs.filter(direction=Transaction.IN).aggregate(
        total=Sum("amount")
    )["total"] or 0

    gastos = qs.filter(direction=Transaction.OUT).aggregate(
        total=Sum("amount")
    )["total"] or 0

    return {
        "ingresos": ingresos,
        "gastos": gastos,
        "resultado": ingresos - gastos,
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

    qs = base_queryset().filter(category__in=categories)

    if entity:
        qs = qs.filter(entity=entity)

    if start and end:
        qs = qs.filter(date__date__gte=start, date__date__lte=end)

    return qs.aggregate(
        total=Sum(
            Case(
                When(direction=Transaction.IN, then=F("amount")),
                When(direction=Transaction.OUT, then=-F("amount")),
                output_field=DecimalField()
            )
        )
    )["total"] or 0


def balance_por_cuenta(account, entity=None):
    qs = base_queryset().filter(account=account)

    if entity:
        qs = qs.filter(entity=entity)

    return qs.aggregate(
        total=Sum(
            Case(
                When(direction=Transaction.IN, then=F("amount")),
                When(direction=Transaction.OUT, then=-F("amount")),
                output_field=DecimalField()
            )
        )
    )["total"] or 0


def consolidated_balance(entities):
    result = {}

    for entity in entities:
        result[entity.name] = (
            base_queryset()
            .filter(entity=entity)
            .aggregate(
                total=Sum(
                    Case(
                        When(direction=Transaction.IN, then=F("amount")),
                        When(direction=Transaction.OUT, then=-F("amount")),
                        output_field=DecimalField()
                    )
                )
            )["total"] or 0
        )

    result["TOTAL"] = sum(result.values())
    return result
