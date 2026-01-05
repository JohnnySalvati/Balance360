from django.db import models


class EconomicEntityLink(models.Model):
    parent = models.ForeignKey(
        "finance.EconomicEntity",
        related_name="children_links",
        on_delete=models.CASCADE,
    )
    child = models.ForeignKey(
        "finance.EconomicEntity",
        related_name="parent_links",
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = ("parent", "child")
        verbose_name = "Entity consolidation"
        verbose_name_plural = "Entity consolidations"

    def __str__(self):
        return f"{self.parent} → {self.child}"
