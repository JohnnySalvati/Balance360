
from apps.finance.services.periods import get_entity_period_status, get_consolidated_period_status, close_period
from apps.finance.services.enums import PeriodStatus
from apps.finance.models import PeriodClose, EconomicEntityLink
from tests.factories import user_factory, entity_for

import pytest

def test_entity_period_open(db):
    user = user_factory()
    entity = entity_for(user)

    status = get_entity_period_status(entity, 2025, 1)

    assert status == PeriodStatus.OPEN

def test_close_period_creates_record(db):
    user = user_factory()
    entity = entity_for(user)

    close_period(entity, 2025, 1, user=user)

    assert PeriodClose.objects.filter(
        entity=entity,
        year=2025,
        month=1,
    ).exists()


def test_close_period_twice_raises(db):
    user = user_factory()
    entity = entity_for(user)

    close_period(entity, 2025, 1, user=user)

    with pytest.raises(ValueError):
        close_period(entity, 2025, 1, user=user)

def test_consolidated_partial(db):
    user = user_factory()
    parent = entity_for(user, "Johnny")

    child1 = entity_for(user_factory("casa"), "Casa")
    child2 = entity_for(user_factory("insoft"), "InSoft")

    EconomicEntityLink.objects.create(parent=parent, child=child1)
    EconomicEntityLink.objects.create(parent=parent, child=child2)

    close_period(child1, 2025, 1, user=user)

    status = get_consolidated_period_status(parent, 2025, 1)

    assert status == PeriodStatus.PARTIAL
