from django.contrib import admin, messages

from apps.finance.models.classification_rule import ClassificationRule
from apps.finance.services.rule_applier import apply_rule
from core.apps.finance.services.classification.preview import preview_rule_impact
@admin.register(ClassificationRule)
class ClassificationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "pattern",
        "entity",
        "category",
        "confidence",
        "is_active",
    )

    list_filter = (
        "is_active",
        "entity",
        "category",
    )

    search_fields = ("pattern",)

    actions = ["preview_impact", "reapply_rules"]

    @admin.action(description="Reaplicar regla(s) seleccionada(s)")
    def reapply_rules(self, request, queryset):
        total = 0

        for rule in queryset:
            if not rule.is_active:
                continue

            total += apply_rule(rule)

        self.message_user(
            request,
            f"{total} transacciones reclasificadas.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Vista previa de impacto")
    def preview_impact(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Seleccione exactamente una regla para ver el impacto.",
                level="warning",
            )
            return

        rule = queryset.first()
        result = preview_rule_impact(rule)

        msg = (
            f"Regla: '{rule.pattern}'\n"
            f"Coinciden con el patrón: {result['matched']}\n"
            f"Se modificarían: {result['would_change']}\n"
            f"(las clasificaciones manuales están protegidas)"
        )

        self.message_user(request, msg)
