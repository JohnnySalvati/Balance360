from django.contrib.contenttypes.models import ContentType
from apps.finance.models import EconomicEntity
from apps.accounts.models import User
from apps.organizations.models import Membership, Organization
from django.contrib.auth.models import AbstractUser


def get_entities_for_user(user: AbstractUser):
    # Entidad personal
    user_ct = ContentType.objects.get_for_model(User)
    entities = EconomicEntity.objects.filter(
        content_type=user_ct,
        object_id=user.pk,
    )

    # Entidades de organizaciones donde es miembro
    org_ct = ContentType.objects.get_for_model(Organization)
    org_ids = Membership.objects.filter(
        user=user
    ).values_list("organization_id", flat=True)

    org_entities = EconomicEntity.objects.filter(
        content_type=org_ct,
        object_id__in=org_ids,
    )

    return entities.union(org_entities)
