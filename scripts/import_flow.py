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
from balance360.matching import find_best_rule

def parse_sheet(wb: Workbook, ws_name: str) -> tuple[list[dict], list[dict]]:
    ws = wb[ws_name]
    valid_rows = []
    skipped_rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        date_val, description, debit, credit, *rest = row
        if (
            not isinstance(date_val, datetime) or 
            not isinstance(debit, (int, float)) and not isinstance(credit, (int, float))
        ):
            skipped_rows.append({
                'date': date_val, 
                'description': description or '(sin descripcion)',
                'debit': debit,
                'credit': credit
            })
        else:
            if isinstance(debit, (int, float)):
                valid_rows.append({
                    'date': date_val,
                    'description': description or '(sin descripcion)',
                    'amount': debit,
                    'transaction_type': TransactionType.expense
                })
            if isinstance(credit, (int, float)):
                valid_rows.append({
                    'date': date_val,
                    'description': description or '(sin descripcion)',
                    'amount': credit,
                    'transaction_type': TransactionType.income
                })
    return (valid_rows, skipped_rows)

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
   
wb = load_workbook('Planilla de Flujo 2026-01.xlsx', data_only=True)

with SessionLocal() as db:
    rules = load_rules(db)
    accounts = load_accounts(db)
    
    for account in accounts:
        if account.name not in wb.sheetnames:
            print(f"Solapa {account.name} no encontrada, saltando...")
            continue
        valid_rows, skipped_rows = parse_sheet(wb, account.name)
        print(f"Solapa {account.name}: {len(valid_rows)} filas validas, {len(skipped_rows)} filas saltadas...")
        import_sheet(db, valid_rows, account, account.currency, rules)