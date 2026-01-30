
from django.forms import ValidationError

from apps.finance.services.enums import PeriodStatus
from apps.finance.services.periods.status import get_entity_period_status


def assert_can_write(entity, year, month):
    """
    Lanza excepción si no se puede escribir en el período.
    """
    status = get_entity_period_status(entity, year, month)

    if status == PeriodStatus.CLOSED:
        raise ValidationError("El período está cerrado.")

    