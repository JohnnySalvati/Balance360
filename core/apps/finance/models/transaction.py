from django.db import models
from django.conf import settings

from .account import Account
from .entity import EconomicEntity
from .category import Category
from .classification_rule import ClassificationRule
class Transaction(models.Model):
    account = models.ForeignKey(Account, on_delete=models.PROTECT)

    entity = models.ForeignKey(
        EconomicEntity,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )

    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    date = models.DateField()  # índice definido en Meta

    description = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    classification_source = models.CharField(
        max_length=20,
        choices=[
            ("manual", "Manual"),
            ("rule", "Regla"),
        ],
        null=True,
        blank=True,
    )

    applied_rule = models.ForeignKey(
        ClassificationRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applied_transactions",
    )
    class Meta:
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["classification_source"]),
            models.Index(fields=["date", "classification_source"]),  # opcional y MUY útil
        ]
