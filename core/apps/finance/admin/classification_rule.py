from django.contrib import admin

from apps.finance.models.classification_rule import ClassificationRule


@admin.register(ClassificationRule)
class ClassificationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "pattern",
        "category",
        "entity",
        "confidence",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "category",
        "entity",
    )

    search_fields = (
        "pattern",
    )

    list_editable = (
        "is_active",
        "confidence",
    )

    ordering = (
        "-confidence",
        "pattern",
    )
