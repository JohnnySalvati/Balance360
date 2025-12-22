# apps/finance/admin/category.py

from django.contrib import admin
from ..models import Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("indented_name", "is_income")
    list_filter = ("is_income",)
    search_fields = ("name",)

    def indented_name(self, obj):
        level = 0
        parent = obj.parent
        while parent:
            level += 1
            parent = parent.parent
        return "— " * level + obj.name

    indented_name.short_description = "Categoría"
