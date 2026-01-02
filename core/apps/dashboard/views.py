from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from apps.finance.services.permissions import get_entities_for_user
from apps.finance.services.reports import (
    monthly_balance,
    total_by_category,
    balance_por_cuenta,
)
from apps.finance.models import Account, Category


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
        total = total_by_category(cat, entity=entity)
        if total != 0:
            category_labels.append(cat.name)
            category_totals.append(float(abs(total)))

    # --- Distribución por cuenta ---
    account_labels = []
    account_totals = []

    for account in Account.objects.all():
        total = balance_por_cuenta(account, entity=entity)
        if total != 0:
            account_labels.append(account.name)
            account_totals.append(float(total))

    context = {
        "entities": entities,
        "entity": entity,

        "monthly_labels": monthly_labels,
        "monthly_totals": monthly_totals,

        "category_labels": category_labels,
        "category_totals": category_totals,

        "account_labels": account_labels,
        "account_totals": account_totals,
    }

    return render(request, "dashboard/index.html", context)
