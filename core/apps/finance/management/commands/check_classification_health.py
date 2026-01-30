from django.core.management.base import BaseCommand
from apps.finance.services.classification.health import (
    get_classification_health,
)

class Command(BaseCommand):
    help = "Diagnóstico del estado de clasificación de transacciones"

    def handle(self, *args, **options):
        stats = get_classification_health()

        self.stdout.write("")
        self.stdout.write("📊 ESTADO DE CLASIFICACIÓN")
        self.stdout.write(f"Total transacciones: {stats['total']}")
        self.stdout.write(f"Sin clasificar: {stats['unclassified']}")
        self.stdout.write(f"Clasificadas por reglas: {stats['rule']}")
        self.stdout.write(f"Clasificadas manualmente: {stats['manual']}")
        self.stdout.write(f"Clasificación parcial: {stats['partial']}")
        self.stdout.write("")

        if stats["all_classified"]:
            self.stdout.write("✅ Todas las transacciones están clasificadas.")
        else:
            self.stdout.write("⚠️  Hay transacciones sin clasificar.")
