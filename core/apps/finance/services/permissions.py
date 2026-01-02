from django.contrib.contenttypes.models import ContentType
from apps.finance.models import EconomicEntity
from apps.accounts.models import User
from apps.organizations.models import Membership, Organization

from django.db.models import Q

def get_entities_for_user(user):
    user_ct = ContentType.objects.get_for_model(User)
    org_ct = ContentType.objects.get_for_model(Organization)

    org_ids = Membership.objects.filter(
        user=user
    ).values_list("organization_id", flat=True)

    return EconomicEntity.objects.filter(
        Q(content_type=user_ct, object_id=user.id) |
        Q(content_type=org_ct, object_id__in=org_ids)
    )
