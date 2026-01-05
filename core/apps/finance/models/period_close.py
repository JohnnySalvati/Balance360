from django.db import models
from django.conf import settings

from apps.finance.models.entity import EconomicEntity
class PeriodClose(models.Model):
    entity = models.ForeignKey(EconomicEntity,
        on_delete=models.CASCADE,
        related_name="period_closes",
    )
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()

    closed_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )


    ingresos = models.DecimalField(max_digits=14, decimal_places=2)
    egresos = models.DecimalField(max_digits=14, decimal_places=2)
    resultado = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        unique_together = ("entity", "year", "month")
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.entity} {self.year}-{self.month:02d}"
