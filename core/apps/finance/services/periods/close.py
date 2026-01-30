from django.db import IntegrityError

from apps.finance.models import PeriodClose
from apps.finance.services.reports import period_result
from apps.finance.services.periods.consolidation import get_consolidated_period_detail

def close_period(entity, year, month, user=None):
    result = period_result(entity, year, month)

    try:
        PeriodClose.objects.create(
            entity=entity,
            year=year,
            month=month,
            ingresos=result["ingresos"],
            egresos=result["egresos"],
            resultado=result["resultado"],
            closed_by=user,
        )
    except IntegrityError:
        raise ValueError("El período ya está cerrado.")
    
def close_open_entities(entity, year, month, user=None):
    detail = get_consolidated_period_detail(entity, year, month)

    for e in detail["open"]:
        close_period(e, year, month, user=user)

