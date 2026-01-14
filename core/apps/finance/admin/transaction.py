from django.contrib import admin
from django.db import transaction

from apps.finance.models.transaction import Transaction
from apps.finance.models.classification_rule import ClassificationRule
from apps.finance.services.patterns import normalize_pattern
from apps.finance.services.classifier import classify_transaction       

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

    actions = ["learn_entity", "reclassify"]


    def get_queryset(self, request):
        return super().get_queryset(request)

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.full_clean()
        super().delete_model(request, obj)

    @admin.action(description="Aprender entity desde descripción")
    def learn_entity(self, request, queryset):
        print(">>> LEARNING ENTITY FROM DESCRIPTION <<<")
        for tx in queryset:
            if not tx.entity:
                print("SKIPPING TX WITHOUT ENTITY:", tx.id) # type: ignore
                continue

            pattern = normalize_pattern(tx.description)

            if not pattern:
                continue

            with transaction.atomic():
                rule, created = ClassificationRule.objects.get_or_create(
                    pattern=pattern,
                    entity=tx.entity,
                    category=tx.category,
                    defaults={"confidence": 100}
                )
                if not created:
                    rule.confidence = min(rule.confidence + 10, 1000)
                    rule.save(update_fields=["confidence"])

                print(
                    f"RULE {rule.id} | " # type: ignore
                    f"{'CREATED' if created else 'UPDATED'} | "
                    f"confidence={rule.confidence}"
                )

    @admin.action(description="Reclasificar usando reglas")
    def reclassify(self, request, queryset):
        updated = 0

        for tx in queryset:
            if classify_transaction(tx):
                updated += 1

        self.message_user(
            request,
            f"{updated} transacciones reclasificadas"
        )
    