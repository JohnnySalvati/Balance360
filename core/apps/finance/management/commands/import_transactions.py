from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from apps.finance.models.account import Account
from apps.finance.models.transaction import Transaction
from apps.finance.models.category import Category
from apps.finance.models.entity import EconomicEntity
from apps.finance.services.periods import is_period_closed
from apps.finance.exceptions import PeriodClosedError

from decimal import Decimal
import pandas as pd
class Command(BaseCommand):
    help = "Importa transacciones desde un archivo Excel"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Ruta al archivo Excel (.xlsx)")

    def handle(self, *args, **options):
        path = options["file"]

        try:
            df = pd.read_excel(path)
        except Exception as e:
            raise CommandError(f"No se pudo leer el archivo: {e}")

        required_cols = {"date", "account", "entity", "category", "amount"}
        if not required_cols.issubset(df.columns):
            raise CommandError(f"Faltan columnas requeridas: {required_cols}")

        created = 0

        for i, row in df.iterrows():
            try:
                account = Account.objects.get(name=row["account"])
                entity = EconomicEntity.objects.get(name=row["entity"])
                category = Category.objects.get(name=row["category"])

                amount = Decimal(row["amount"])
                if amount == 0:
                    self.stderr.write(f"Fila {i}: monto cero, se omite")
                    continue
                
                raw_date = row["date"]
                parsed_date = pd.to_datetime(raw_date, errors="coerce")
                if pd.isna(parsed_date):
                    self.stderr.write(f"Fila {i}: fecha inválida -> {raw_date}")
                    continue

                if is_period_closed(entity, parsed_date.date()):
                    raise PeriodClosedError(
                        f"Período {parsed_date.month}/{parsed_date.year} cerrado para {entity}"
                    )

                tx = Transaction.objects.create(
                    account=account,
                    entity=entity,
                    category=category,
                    amount=amount,
                    date=pd.to_datetime(row["date"]).date(),
                    description=str(row.get("description", "")),
                )

                created += 1

            except Exception as e:
                self.stderr.write(f"Fila {i} con error: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Importación finalizada. Transacciones creadas: {created}"
        ))
