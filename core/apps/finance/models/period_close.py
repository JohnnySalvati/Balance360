from django.db import models
from apps.finance.models import EconomicEntity


class PeriodClose(models.Model):
    entity = models.ForeignKey(EconomicEntity, on_delete=models.PROTECT)
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()

    closed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("entity", "year", "month")

    def __str__(self):
        return f"{self.entity} {self.month}/{self.year}"
