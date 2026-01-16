
# apps/finance/signals/classification_rule.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from apps.accounts.models import User
from apps.finance.models import EconomicEntity
from apps.finance.services.rule_applier import apply_rule
from apps.organizations.models import Organization

# @receiver(post_save, sender=ClassificationRule)
# def apply_rule_to_existing_transactions(sender, instance, created, **kwargs):
#     if created and instance.is_active:
#         apply_rule(instance)

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
