from import_flow import import_sheet, load_accounts, load_rules, parse_sheet
from openpyxl import load_workbook

from balance360.database import SessionLocal

wb_name = "Planilla de Flujo 2026-01.xlsx"
wb = load_workbook(wb_name, data_only=True)

with SessionLocal() as db:
    rules = load_rules(db)
    accounts = load_accounts(db)
    cash_account = next(a for a in accounts if a.name == "Efectivo")

    valid_rows, skipped_rows, cash_rows, visa_rows = parse_sheet(wb, "Efectivo")

    import_sheet(db, valid_rows, cash_account, rules)
