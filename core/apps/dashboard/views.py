from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from apps.finance.models import Account, Category, EconomicEntity
from apps.finance.services.permissions import get_entities_for_user
from apps.finance.services.entities import get_consolidated_entities
from apps.finance.services.periods import (
    close_period,
    get_period_status,
    period_result
)
from apps.finance.services.reports import (
    monthly_balance,
    total_by_category,
    account_balance,
)

from datetime import date
from calendar import monthrange

@login_required
def dashboard(request):
    entities = get_entities_for_user(request.user)

    # --- entidad seleccionada ---
    entity_id = request.GET.get("entity")

    if entity_id:
        entity = entities.filter(id=entity_id).first()
    else:
        entity = entities.first()

    if not entity:
        return render(request, "dashboard/index.html", {
            "entities": entities,
            "error": "No hay entidades disponibles."
        })
        
    today = date.today()

    years = range(2010, today.year + 1)
    months = range(1, 13)

    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    period_status = get_period_status(
            entity,
            year,
            month,
        ).value

    start = date(year, month, 1)
    end_day = monthrange(year, month)[1]
    end = date(year, month, end_day)

    period = period_result(
        entity,
        year,
        month,
    )

    cat_scope = request.GET.get("cat_scope", "all")
    acc_scope = request.GET.get("acc_scope", "all")

    # --- Balance mensual ---
    monthly = monthly_balance(entity)
    monthly_labels = [m["month"].strftime("%Y-%m") for m in monthly]
    monthly_totals = [float(m["total"]) for m in monthly]

    # Tomamos la categoría raíz "Egresos"
    egresos = Category.objects.get(name="Egresos")

    # Subcategorías directas (nivel 2)
    expense_categories = egresos.children.all() # type: ignore[attr-defined]

    category_labels = []
    category_totals = []

    for cat in expense_categories:
        if cat_scope == "period":
            total = total_by_category(
                cat,
                entity=entity,
                start=start,
                end=end,
            )
        else:
            total = total_by_category(cat, entity=entity)

        if total != 0:
            category_labels.append(cat.name)
            category_totals.append(float(abs(total)))

    # --- Distribución por cuenta ---
    account_labels = []
    account_totals = []

    for account in Account.objects.all():
        qs_kwargs = {}

        if acc_scope == "period":
            qs_kwargs["start"] = start
            qs_kwargs["end"] = end

        total = account_balance(
            account,
            entity=entity,
            **qs_kwargs,
        )

        if total != 0:
            account_labels.append(account.name)
            account_totals.append(float(total))


    context = {
        "entities": entities,
        "entity": entity,

        "context_cat_scope": cat_scope,
        "context_acc_scope": acc_scope,

        "context_year": year,
        "context_month": month,

        "monthly_labels": monthly_labels,
        "monthly_totals": monthly_totals,

        "category_labels": category_labels,
        "category_totals": category_totals,

        "account_labels": account_labels,
        "account_totals": account_totals,

        "period": period,
        "period_status": period_status,
        
        "context_years": years,
        "context_months": months,
    }

    return render(request, "dashboard/index.html", context)


@login_required
def close_period_view(request):
    entity_id = request.POST["entity"]
    year = int(request.POST["year"])
    month = int(request.POST["month"])

    entity = EconomicEntity.objects.get(id=entity_id)

    close_period(entity, year, month)
    return redirect(request.META.get("HTTP_REFERER", "/"))
