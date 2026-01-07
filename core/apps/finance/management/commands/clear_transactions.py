from django.core.management.base import BaseCommand
from apps.finance.models import Transaction
from apps.finance.models.entity import EconomicEntity

class Command(BaseCommand):
    help = "Elimina transacciones por entidad y/o período"

    def add_arguments(self, parser):
        parser.add_argument("--entity", type=str, help="Nombre de la entidad")
        parser.add_argument("--year", type=int)
        parser.add_argument("--month", type=int)
        parser.add_argument("--all", action="store_true")

    def handle(self, *args, **opts):
        qs = Transaction.objects.all()

        if opts["entity"]:
            qs = qs.filter(entity__name=opts["entity"])

        if opts["year"] and opts["month"]:
            qs = qs.filter(
                date__year=opts["year"],
                date__month=opts["month"],
            )

        if not opts["all"] and not qs.exists():
            self.stdout.write("No hay transacciones para borrar.")
            return

        count = qs.count()
        qs.delete()

        self.stdout.write(
            self.style.SUCCESS(f"{count} transacciones eliminadas")
        )
