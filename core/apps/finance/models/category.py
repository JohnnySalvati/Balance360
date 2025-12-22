from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.PROTECT
    )

    is_income = models.BooleanField()

    def __str__(self):
        return self.full_name()

    def full_name(self):
        if self.parent:
            return f"{self.parent.full_name()} > {self.name}"
        return self.name
