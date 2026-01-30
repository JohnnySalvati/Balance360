# apps/finance/services/importers/bank_excel.py

from decimal import Decimal, ROUND_HALF_UP
import pandas as pd
import re

from apps.finance.models import (
    Account,
    Transaction,
    Category,
    EconomicEntity,
    ClassificationRule,
)


class BankExcelImporter:
    CATEGORY_RULES = [
        (["visa"], "Gastos"),
        (["prosegur"], "Gastos"),
        (["sircreb"], "Impuestos"),
        (["ib "], "Impuestos"),
        (["comision mep"], "Comisiones MEP"),
        (["comision"], "Comisiones"),
        (["compra u$s mep", "venta u$s mep"], "Inversiones"),
        (
            [
                "a mp", "de mp",
                "al ciudad", "del ciudad",
                "deposito", "extraccion",
                "al frances", "del frances",
            ],
            "Transferencias",
        ),
    ]

    PROVIDER_CATEGORY_MAP = {
        "prosegur": "Gastos",
        "farmacia": "Gastos",
        "pescaderia": "Gastos",
        "arreglo auto": "Gastos",
    }

    SHEET_ACCOUNT_MAP = {
        "Frances": "Banco Frances (ARS)",
        "Ciudad": "Banco Ciudad (ARS)",
        "MP": "Mercado Pago (ARS)",
    }

    def __init__(self):
        self._category_cache = {}

    # ======================
    # API pública
    # ======================

    def import_file(self, path: str):
        xls = pd.ExcelFile(path)

        sheet_names = [
            str(s).replace("\xa0", "").strip()
            for s in xls.sheet_names
        ]

        valid_sheets = {
            key: acc
            for key, acc in self.SHEET_ACCOUNT_MAP.items()
            if key in sheet_names
        }

        if not valid_sheets:
            raise ValueError("No se encontraron solapas válidas")

        for sheet_key, account_name in valid_sheets.items():
            account = Account.objects.get(name=account_name)
            df = pd.read_excel(xls, sheet_name=sheet_key)
            self.import_sheet(df, account)

    def import_sheet(self, df, account):
        for i, row in df.iterrows():
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
                )
                tx.full_clean()
                tx.save()

    # ======================
    # Helpers
    # ======================

    def parse_money(self, value):
        if pd.isna(value):
            return None

        if isinstance(value, (int, float, Decimal)):
            return Decimal(value).quantize(Decimal("0.01"))

        value = re.sub(r"[^\d,.\-]", "", str(value).strip())

        if "," in value and "." in value:
            value = value.replace(",", "")

        try:
            return Decimal(value).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        except Exception:
            return None

    def extract_movements(self, row):
        movements = []

        debito = self.parse_money(row.get("Debito"))
        credito = self.parse_money(row.get("Credito"))

        if debito:
            movements.append({"amount": -abs(debito)})

        if credito:
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
            if rule.pattern in text:
                return rule.entity

        return None

    def resolve_category(self, description):
        text = description.lower()

        for keywords, category_name in self.CATEGORY_RULES:
            if any(k in text for k in keywords):
                return self.get_category(category_name)

        for key, category in self.PROVIDER_CATEGORY_MAP.items():
            if key in text:
                return self.get_category(category)

        rules = (
            ClassificationRule.objects
            .filter(is_active=True, category__isnull=False)
            .order_by("-confidence", "pattern")
        )

        for rule in rules:
            if rule.pattern in text:
                return rule.category

        return None

    def get_category(self, name):
        if name not in self._category_cache:
            self._category_cache[name] = Category.objects.get(name=name)
        return self._category_cache[name]
