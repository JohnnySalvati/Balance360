# apps/finance/management/commands/import_transaction.py

from django.core.management.base import BaseCommand, CommandError
from apps.finance.services.importers.bank_excel import BankExcelImporter


class Command(BaseCommand):
    help = "Importa transacciones desde un archivo Excel"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str)

    def handle(self, *args, **options):
        try:
            importer = BankExcelImporter()
            importer.import_file(options["file"])
            self.stdout.write(self.style.SUCCESS("Importación finalizada"))
        except Exception as e:
            raise CommandError(str(e))
