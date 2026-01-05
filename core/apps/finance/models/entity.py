from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from typing import TYPE_CHECKING

class EconomicEntity(models.Model):
    if TYPE_CHECKING:
        id: int
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("content_type", "object_id")

    def __str__(self):
        return self.name
