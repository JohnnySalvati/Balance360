from apps.finance.services.enums import PeriodStatus
from apps.finance.models import PeriodClose
from apps.finance.services.entities import get_consolidated_entities

def get_consolidated_period_status(entity, year, month) -> PeriodStatus:
    """
    Evalúa una entidad.
    Si tiene hijas, consolida.
    Puede devolver OPEN / PARTIAL / CLOSED.
    """
    entities = get_consolidated_entities(entity)
  
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

def get_consolidated_period_detail(entity, year, month):
    """
    Devuelve el estado del período y el detalle por entidad hija.
    SOLO para UI.
    """
    entities = get_consolidated_entities(entity)

    closed_entities = PeriodClose.objects.filter(
        entity__in=entities,
        year=year,
        month=month,
    ).values_list("entity_id", flat=True)

    closed = []
    open_ = []

    for e in entities:
        if e.id in closed_entities:
            closed.append(e)
        else:
            open_.append(e)

    status = get_consolidated_period_status(entity, year, month)

    return {
        "status": status,
        "closed": closed,
        "open": open_,
    }
