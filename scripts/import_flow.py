import uuid
from decimal import Decimal
from openpyxl import load_workbook, Workbook
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from balance360 import models
from balance360.models import Account, Currency, ImportRule, Transaction
from balance360.enums import TransactionType
from balance360.database import SessionLocal
from balance360.matching import find_best_rule, extract_amount

def clean_work_book(wb: Workbook, ws_name: str):
    if ws_name in wb.sheetnames: del wb[ws_name]
    ws = wb.create_sheet(ws_name)
    headers = ['Fecha', 'Descripcion', 'Debito', 'Credito', 'Cuenta']
    ws.append(headers)

def export_rows(wb: Workbook, rows, sheet: str):
    ws = wb[sheet]    
    for row in rows:
        ws.append([row['date'], row['description'], row['debit'], row['credit'], row['account']])
    
def parse_sheet(wb: Workbook, ws_name: str) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    ws = wb[ws_name]
    valid_rows = []
    skipped_rows = []
    cash_rows = []
    visa_rows = []
    
    for row in ws.iter_rows(min_row=2, values_only=True):
        date_val, description, debit, credit, *rest = row
        if description:
            description = str(description)
        else:
            description = '(sin descripcion)'

        if not isinstance(date_val, datetime):
            skipped_rows.append({
                'date': date_val, 
                'description': description,
                'debit': debit,
                'credit': credit
            })
        elif not isinstance(debit, (int, float)) and not isinstance(credit, (int, float)):
            if 'VISA' in description:
                amount = extract_amount(description)
                if amount is not None:
                    visa_rows.append({
                        'date': date_val, 
                        'description': description,
                        'amount': amount,
                        'transaction_type': TransactionType.expense
                    })
                else:
                    skipped_rows.append({
                        'date': date_val, 
                        'description': description,
                        'debit': 0,
                        'credit': 0,
                        'account': ws_name
                    })
            else:
                cash_rows.append({
                    'date': date_val, 
                    'description': description,
                    'debit': 0,
                    'credit': 0,
                    'account': ws_name
                })
        else:
            if isinstance(debit, (int, float)) and debit > 0:
                valid_rows.append({
                    'date': date_val,
                    'description': description or '(sin descripcion)',
                    'amount': debit,
                    'transaction_type': TransactionType.expense
                })
            if isinstance(credit, (int, float)) and credit > 0:
                valid_rows.append({
                    'date': date_val,
                    'description': description or '(sin descripcion)',
                    'amount': credit,
                    'transaction_type': TransactionType.income
                })
    return (valid_rows, skipped_rows, cash_rows, visa_rows)

def load_rules(db: Session) -> list[ImportRule]:
    rules = db.execute(select(ImportRule)).scalars().all()
    return list(rules)

def load_accounts(db: Session) -> list[Account]:
    accounts = db.execute(select(Account)).scalars().all()
    return list(accounts)

def load_currency(db: Session) -> dict:
    currencies_dict = {}
    currencies = db.execute(select(Currency)).scalars().all()
    for currency in currencies:
        currencies_dict[currency.code] = currency
    return currencies_dict

def import_sheet(db: Session, rows: list[dict], account: Account, currency: Currency, rules: list[ImportRule]):
    for row in rows:
        import_rule = find_best_rule(row['description'], row['transaction_type'], rules)
        transaction_dict = {
            'id': uuid.uuid4(),
            'date': row['date'],
            'description': row['description'],
            'amount': Decimal(str(row['amount'])),
            'type': row['transaction_type'],
            'account_id': account.id,
            'entity_id': import_rule.entity_id if import_rule else None,
            'currency_id': currency.id,
            'contact_id': import_rule.contact_id if import_rule else None,
            'category_id': import_rule.category_id if import_rule else None,
            'is_manual': False,
            'is_transfer': import_rule.is_transfer if import_rule else False
        }

        stmt = pg_insert(Transaction).values(**transaction_dict).on_conflict_do_nothing(
            constraint="uq_transaction"
        )
        db.execute(stmt)
    db.commit()

if __name__ == "__main__":
    wb_name = 'Planilla de Flujo 2026-01.xlsx'
    wb = load_workbook(wb_name, data_only=True)

    with SessionLocal() as db:
        rules = load_rules(db)
        accounts = load_accounts(db)
        visa_account = next(a for a in accounts if a.name == 'VISA Ciudad')
        accounts_to_import = ['Frances', 'Ciudad', 'MP', 'VISA Ciudad']
        
        clean_work_book(wb, 'Efectivo')
        clean_work_book(wb, 'VISA Ciudad')

        for account in accounts:
            if account.name not in accounts_to_import:
                continue
            valid_rows, skipped_rows, cash_rows, visa_rows = parse_sheet(wb, account.name)
            if cash_rows: export_rows(wb, cash_rows, 'Efectivo')
            
            print(f"Solapa {account.name}: {len(valid_rows)} filas validas, {len(skipped_rows)} filas saltadas, {len(cash_rows)} filas de efectivo creadas")
            import_sheet(db, valid_rows, account, account.currency, rules)
            if visa_rows:
                import_sheet(db, visa_rows, visa_account, visa_account.currency, rules)
        wb.save(wb_name)

        
