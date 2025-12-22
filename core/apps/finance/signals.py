from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.accounts.models import User
from apps.organizations.models import Organization
from .models import EconomicEntity



@receiver(post_save, sender=User)
def create_economic_entity_for_user(sender, instance, created, **kwargs):
    if not created:
        return

    content_type = ContentType.objects.get_for_model(User)

    EconomicEntity.objects.create(
        content_type=content_type,
        object_id=instance.id,
        name=f"{instance.get_full_name() or instance.username} (Personal)",
    )


@receiver(post_save, sender=Organization)
def create_economic_entity_for_organization(sender, instance, created, **kwargs):
    if not created:
        return

    content_type = ContentType.objects.get_for_model(Organization)

    EconomicEntity.objects.create(
        content_type=content_type,
        object_id=instance.id,
        name=instance.name,
    )
