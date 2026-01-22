from django.contrib import admin

from apps.finance.models.transaction import Transaction
from apps.finance.services.rule_learning import reinforce_rule_from_transaction

print(">>> CARGANDO TransactionAdmin <<<")
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "entity",
        "account",
        "description",
        "category",
        "amount",
    )

    list_filter = (
        "account",
        "entity",
        "category",
        "date",
    )

    list_editable = (
        "entity",
    )

    search_fields = ("description",)

    date_hierarchy = "date"

    ordering = ("-date",)

    actions = ["learn_entity"]


    def get_queryset(self, request):
        return super().get_queryset(request)

    def save_model(self, request, obj, form, change):
        from apps.finance.services.rule_learning import penalize_rule

        if change and obj.classification_source == "rule":
            if "entity" in form.changed_data or "category" in form.changed_data:
                penalize_rule(obj.applied_rule)  # ver nota abajo
                obj.classification_source = "manual"

        obj.full_clean()
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.full_clean()
        super().delete_model(request, obj)

    

@admin.action(
    description="Aprender regla de entidad y categoría desde descripción"
)
def learn_entity(self, request, queryset):
    learned = 0

    for tx in queryset:
        rule = reinforce_rule_from_transaction(tx)
        if rule:
            learned += 1

    self.message_user(
        request,
        f"{learned} regla(s) aprendidas o reforzadas correctamente.",
    )
