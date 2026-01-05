from django.contrib import admin
from django.core.exceptions import ValidationError, PermissionDenied

from apps.finance.services.periods import get_period_status
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
        year = obj.date.year
        month = obj.date.month
        if get_period_status(obj.entity, year, month) == PeriodStatus.CLOSED:
            raise PermissionDenied("Período cerrado.")
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        year = obj.date.year
        month = obj.date.month
        if get_period_status(obj.entity, year, month) == PeriodStatus.CLOSED:
            raise PermissionDenied("Período cerrado.")
        super().delete_model(request, obj)
