from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from apps.finance.models import (
    EconomicEntity,
    PeriodClose,
    Transaction,
    Account,
    Category,
)

from datetime import date

User = get_user_model()

def user_factory(username="user"):
    return User.objects.create_user(username=username, password="test")

def entity_for(obj, name=None):
    ct = ContentType.objects.get_for_model(obj)

    entity, _ = EconomicEntity.objects.get_or_create(
        content_type=ct,
        object_id=obj.id,
        defaults={
            "name": name or str(obj),
        },
    )
    return entity
