from django.contrib import admin
from ..models import Transaction
from django.core.exceptions import ValidationError

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

def clean(self):
    if self.amount == 0:
        raise ValidationError("El monto no puede ser cero.")