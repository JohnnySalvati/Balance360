from django.db import models

from apps.finance.models.category import Category
from apps.finance.models.entity import EconomicEntity


class ClassificationRule(models.Model):
    """
    Regla aprendida para clasificar transacciones
    en base a la descripción.
    """

    pattern = models.CharField(
        max_length=255,
        help_text="Texto normalizado que debe aparecer en la descripción"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="classification_rules"
    )

    entity = models.ForeignKey(
        EconomicEntity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classification_rules"
    )

    is_active = models.BooleanField(default=True)

    confidence = models.PositiveSmallIntegerField(
        default=100,
        help_text="Prioridad de la regla (mayor = se aplica primero)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Regla de clasificación"
        verbose_name_plural = "Reglas de clasificación"
        ordering = ["-confidence", "pattern"]
        unique_together = ("pattern", "category")

    def __str__(self):
        return f"{self.pattern} → {self.category.name}"
