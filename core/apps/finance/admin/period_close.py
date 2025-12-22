from django.contrib import admin
from apps.finance.models.period_close import PeriodClose

@admin.register(PeriodClose)
class PeriodCloseAdmin(admin.ModelAdmin):
    list_display = ("entity", "month", "year", "closed_at")
    list_filter = ("entity", "year", "month")
    ordering = ("-year", "-month")

    def has_delete_permission(self, request, obj=None):
        return False
