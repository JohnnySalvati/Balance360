# apps/finance/admin/account.py

from django.contrib import admin
from ..models import Account

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "currency", "is_active")
    list_filter = ("type", "currency", "is_active")
    search_fields = ("name",)
