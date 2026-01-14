from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.finance.models.classification_rule import ClassificationRule
from apps.finance.models.transaction import Transaction
from apps.finance.services.classifier import classify_transaction
from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.finance.models import EconomicEntity

@receiver(post_save, sender=ClassificationRule)
def apply_rule_to_existing_transactions(sender, instance, created, **kwargs):
    """
    Cuando se crea o modifica una regla activa,
    se reintentan clasificar transacciones pendientes.
    """
    if not instance.is_active:
        return

    # Solo impactamos transacciones NO resueltas
    qs = Transaction.objects.filter(
        description__icontains=instance.pattern
    ).filter(
        entity__isnull=True
    ) | Transaction.objects.filter(
        description__icontains=instance.pattern,
        category__isnull=True
    )

    for tx in qs:
        classify_transaction(tx)

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
