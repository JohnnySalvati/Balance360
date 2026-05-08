import uuid
from decimal import Decimal
from openpyxl import load_workbook, Workbook
from datetime import datetime
from sqlalchemy import select
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

def load_accounts(db: Session) -> dict:
    accounts_dict = {}
    accounts = db.execute(select(Account)).scalars().all()
    for account in accounts:
        accounts_dict[account.name] = account
    return accounts_dict

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
            'date': row['date'],
            'description': row['description'],
            'amount': Decimal(str(row['amount'])),
            'type': row['transaction_type'],
            'from_account_id': None if row['transaction_type'] == TransactionType.income else account.id,
            'to_account_id': None if row['transaction_type'] == TransactionType.expense else account.id,
            'entity_id': import_rule.entity_id if import_rule else None,
            'currency_id': currency.id,
            'contact_id': import_rule.contact_id if import_rule else None,
            'category_id': import_rule.category_id if import_rule else None,
            'is_manual': False
        }
        transaction = Transaction(**transaction_dict)
        db.add(transaction)
    db.commit()
   
wb = load_workbook('Planilla de Flujo 2026-01.xlsx', data_only=True)

with SessionLocal() as db:
    rules = load_rules(db)
    accounts = load_accounts(db)
    currencies = load_currency(db)

    account = accounts["Frances"]
    currency = currencies["ARS"]
    valid_rows, skipped_rows = parse_sheet(wb, account.name)

    for row in valid_rows:
        print(row)

    import_sheet(db, valid_rows, account, currency, rules)