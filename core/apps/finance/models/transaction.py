from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

from .account import Account
from .entity import EconomicEntity
from .category import Category
class Transaction(models.Model):
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    entity = models.ForeignKey(EconomicEntity, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} {self.amount}"

    def clean(self):
        from apps.finance.services.periods import assert_can_write
        
        if not self.entity or not self.date:
            return

        assert_can_write(
            self.entity,
            self.date.year,
            self.date.month,
        )

        if self.amount == 0:
            raise ValidationError("El monto no puede ser cero.")
