from django.db import models
from .account import Account
from .entity import EconomicEntity
from .category import Category
from django.core.exceptions import ValidationError
from apps.finance.models.period_close import PeriodClose


class Transaction(models.Model):
    IN = "in"
    OUT = "out"

    DIRECTION_CHOICES = [
        (IN, "Ingreso"),
        (OUT, "Egreso"),
    ]

    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    entity = models.ForeignKey(EconomicEntity, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)

    date = models.DateTimeField()
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def signed_amount(self):
        return self.amount if self.direction == self.IN else -self.amount

    def __str__(self):
        return f"{self.date.date()} {self.amount}"


def clean(self):
    if self.amount <= 0:
        raise ValidationError("El monto debe ser mayor a cero.")
