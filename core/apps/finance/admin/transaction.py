from django.contrib import admin
from django.core.exceptions import ValidationError, PermissionDenied

from ..models import Transaction
from apps.finance.services.enums import PeriodStatus

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "entity",
        "account",
        "category",
        "amount",
    )

    list_filter = (
        "account",
        "entity",
        "category",
        "date",
    )

    search_fields = ("description",)

    date_hierarchy = "date"

    ordering = ("-date",)

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.full_clean()
        super().delete_model(request, obj)
