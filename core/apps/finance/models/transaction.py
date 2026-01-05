from django.db import models
from django.core.exceptions import ValidationError

from apps.finance.services.enums import PeriodStatus
from .account import Account
from .entity import EconomicEntity
from .category import Category

class Transaction(models.Model):
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    entity = models.ForeignKey(EconomicEntity, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    date = models.DateTimeField()
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date.date()} {self.amount}"

    def clean(self):
        if self.amount == 0:
            raise ValidationError("El monto no puede ser cero.")
        
        from apps.finance.services.periods import get_period_status

        if self.date and self.entity:
            year = self.date.year
            month = self.date.month
            if get_period_status(self.entity, year, month) == PeriodStatus.CLOSED:
                raise ValidationError("El período está cerrado.")
