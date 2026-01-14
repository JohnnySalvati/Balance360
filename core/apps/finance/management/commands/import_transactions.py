from django.core.management.base import BaseCommand, CommandError

from apps.finance.models.account import Account
from apps.finance.models.transaction import Transaction
from apps.finance.models.category import Category
from apps.finance.models.entity import EconomicEntity
from apps.finance.models.classification_rule import ClassificationRule

from decimal import Decimal, ROUND_HALF_UP
import pandas as pd
import re
class Command(BaseCommand):
    help = "Importa transacciones desde un archivo Excel"

    CATEGORY_RULES = [
        (["visa"], "Gastos"),
        (["prosegur"], "Gastos"),
        (["sircreb"], "Impuestos"),
        (["ib "], "Impuestos"),
        (["comision mep"], "Comisiones MEP"),
        (["comision"], "Comisiones"),
        (["compra u$s mep", "venta u$s mep"], "Inversiones"),
        (["a mp", "de mp", "al ciudad", "del ciudad", "deposito", "extraccion"], "Transferencias"),
    ]

    PROVIDER_CATEGORY_MAP = {
        "prosegur": "Gastos",
        "farmacia": "Gastos",
        "pescaderia": "Gastos",
        "arreglo auto": "Gastos",
    }

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Ruta al archivo Excel (.xlsx)")

    def handle(self, *args, **options):
        path = options["file"]

        SHEET_ACCOUNT_MAP = {
            "Frances": "Banco Frances (ARS)",
            "Ciudad": "Banco Ciudad (ARS)",
            "MP": "Mercado Pago (ARS)",
        }

        xls = pd.ExcelFile(path)
    
        sheet_names = [
            str(s).replace("\xa0", "").strip()
            for s in xls.sheet_names
        ]

        valid_sheets = {
            key: acc
            for key, acc in SHEET_ACCOUNT_MAP.items()
            if key in sheet_names
        }

        if not valid_sheets:
            raise CommandError("No se encontraron solapas válidas (bbva, ciudad, mp)")

        for sheet_key, account_name in valid_sheets.items():
            try:
                account = Account.objects.get(name=account_name)
            except Account.DoesNotExist:
                raise CommandError(f"No existe la cuenta: {account_name}")

            df = pd.read_excel(xls, sheet_name=sheet_key)
            self.stdout.write(f"Importando solapa '{sheet_key}' → {account_name}")

            self.import_sheet(df, account)

    def import_sheet(self, df, account):
        for i, row in df.iterrows():
            try:
                parsed_date = pd.to_datetime(row.get("date"), errors="coerce")
                if pd.isna(parsed_date):
                    continue

                description = str(row.get("description", "")).strip()
                if not description:
                    continue

                movements = self.extract_movements(row)
                if not movements:
                    continue

                entity = self.resolve_entity(description)
                category = self.resolve_category(description)

                for m in movements:
                    tx = Transaction(
                        account=account,
                        entity=entity,
                        category=category,
                        amount=m["amount"],
                        date=parsed_date.date(),
                        description=description,
                        created_by=None,
                    )
                    tx.full_clean()
                    tx.save()

            except Exception as e:
                self.stderr.write(f"{account.name} fila {i}: {e}")

    # -------------------------
    # Métodos auxiliares
    # -------------------------

    def parse_money(self, value):
        if pd.isna(value):
            return None

        if isinstance(value, (int, float, Decimal)):
            return Decimal(value).quantize(Decimal("0.01"))

        value = str(value).strip()
        if not value:
            return None

        value = re.sub(r"[^\d,.\-]", "", value)

        if "," in value and "." in value:
            value = value.replace(",", "")

        try:
            return Decimal(value).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
        except Exception:
            return None

    def extract_movements(self, row):
        movements = []

        debito = self.parse_money(row.get("Debito"))
        credito = self.parse_money(row.get("Credito"))

        if debito and debito != 0:
            movements.append({"amount": -abs(debito)})

        if credito and credito != 0:
            movements.append({"amount": abs(credito)})

        return movements

    def resolve_entity(self, description):
        text = description.lower()

        rules = (
            ClassificationRule.objects
            .filter(is_active=True, entity__isnull=False)
            .order_by("-confidence", "pattern")
        )

        for rule in rules:
            if rule.pattern.lower() in text:
                return rule.entity

        return None  # explícitamente no resuelta

    def resolve_category(self, description):
        text = description.lower()

        for keywords, category_name in self.CATEGORY_RULES:
            for kw in keywords:
                if kw in text:
                    return self.get_category(name=category_name)

        for key, category in self.PROVIDER_CATEGORY_MAP.items():
            if key in text:
                return self.get_category(name=category)
            
        rules = (
            ClassificationRule.objects
            .filter(is_active=True)
            .order_by("-confidence", "pattern")
        )

        for rule in rules:
            if rule.pattern.lower() in text:
                return rule.category

        return None  # explícitamente no resuelta

    def get_category(self, name):
        if not hasattr(self, "_category_cache"):
            self._category_cache = {}
        if name not in self._category_cache:
            self._category_cache[name] = Category.objects.get(name=name)
        return self._category_cache[name]
    
