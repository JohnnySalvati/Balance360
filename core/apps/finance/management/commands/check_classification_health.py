from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.finance.models.transaction import Transaction


class Command(BaseCommand):
    help = "Diagnóstico del estado de clasificación de transacciones"

    def handle(self, *args, **options):
        total = Transaction.objects.count()

        unclassified = Transaction.objects.filter(
            entity__isnull=True,
            category__isnull=True,
        ).count()

        rule_classified = Transaction.objects.filter(
            classification_source="rule"
        ).count()

        manual_classified = Transaction.objects.filter(
            classification_source="manual"
        ).count()

        partial = Transaction.objects.filter(
            Q(entity__isnull=True, category__isnull=False) |
            Q(entity__isnull=False, category__isnull=True)
        ).count()

        self.stdout.write("")
        self.stdout.write("📊 ESTADO DE CLASIFICACIÓN")
        self.stdout.write(f"Total transacciones: {total}")
        self.stdout.write(f"Sin clasificar: {unclassified}")
        self.stdout.write(f"Clasificadas por reglas: {rule_classified}")
        self.stdout.write(f"Clasificadas manualmente: {manual_classified}")
        self.stdout.write(f"Clasificación parcial: {partial}")
        self.stdout.write("")

        if unclassified:
            self.stdout.write("⚠️  Hay transacciones sin clasificar.")
        else:
            self.stdout.write("✅ Todas las transacciones están clasificadas.")
