# apps/finance/admin/entity.py

from django.contrib import admin
from ..models import EconomicEntity

@admin.register(EconomicEntity)
class EconomicEntityAdmin(admin.ModelAdmin):
    list_display = ("name", "content_type", "object_id")
    readonly_fields = ("content_type", "object_id", "name")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
