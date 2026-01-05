from django.db import IntegrityError
from django.core.exceptions import ValidationError

from apps.finance.models import PeriodClose
from apps.finance.services.reports import period_result
from apps.finance.services.enums import PeriodStatus
from apps.finance.services.entities import get_consolidated_entities

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


def get_entity_period_status(entity, year, month) -> PeriodStatus:
    """
    Evalúa SOLO la entidad hoja.
    Devuelve OPEN o CLOSED.
    """
    return (
        PeriodStatus.CLOSED
        if PeriodClose.objects.filter(
            entity=entity,
            year=year,
            month=month,
        ).exists()
        else PeriodStatus.OPEN
    )

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

def assert_can_write(entity, year, month):
    """
    Lanza excepción si no se puede escribir en el período.
    """
    status = get_entity_period_status(entity, year, month)

    if status == PeriodStatus.CLOSED:
        raise ValidationError("El período está cerrado.")

    