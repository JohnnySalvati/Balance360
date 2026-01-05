from django.db import IntegrityError

from apps.finance.models import PeriodClose
from apps.finance.services.reports import period_result
from apps.finance.services.enums import PeriodStatus

def close_period(entity, year, month):
    result = period_result(entity, year, month)

    try:
        PeriodClose.objects.create(
            entity=entity,
            year=year,
            month=month,
            ingresos=result["ingresos"],
            egresos=result["egresos"],
            resultado=result["resultado"],
        )
    except IntegrityError:
        raise ValueError("El período ya está cerrado.")
    
def get_period_status(entity, year, month) -> PeriodStatus:
    """
    Devuelve el estado del período para:
    - una entidad simple
    - una entidad consolidada (con hijas)
    """

    # Caso 1: entidad consolidada (tiene hijas)
    children = getattr(entity, "children", None)

    if children and children.exists():
        entities = list(children.all())
    else:
        entities = [entity]

    total = len(entities)

    closed = PeriodClose.objects.filter(
        entity__in=entities,
        year=year,
        month=month,
    ).count()

    if closed == 0:
        return PeriodStatus.OPEN
    if closed == total:
        return PeriodStatus.CLOSED
    return PeriodStatus.PARTIAL
