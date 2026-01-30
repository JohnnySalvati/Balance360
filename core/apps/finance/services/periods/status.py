
from apps.finance.services.enums import PeriodStatus

from apps.finance.models import PeriodClose

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

