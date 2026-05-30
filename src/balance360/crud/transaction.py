import uuid
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from balance360.enums import TransactionType
from balance360.models.transaction import Transaction
from balance360.schemas.transaction import TransactionCreate, TransactionUpdate

def get_all(
        db: Session,
        date_from: date|None = None,
        date_to: date|None = None,
        entity_id: uuid.UUID|None = None,
        account_id: uuid.UUID|None = None,
        transaction_type: TransactionType|None = None,
        category_id: uuid.UUID|None = None,
        unclassified: bool = False,
        description: str = ""
        ) -> list[Transaction]:
    stmt = select(Transaction)
    if date_from: stmt = stmt.where(Transaction.date >= date_from)
    if date_to: stmt = stmt.where(Transaction.date <= date_to)
    if entity_id: stmt = stmt.where(Transaction.entity_id == entity_id)
    if account_id: stmt = stmt.where(Transaction.account_id == account_id)
    if transaction_type: stmt = stmt.where(Transaction.type == transaction_type)
    if category_id: stmt = stmt.where(Transaction.category_id == category_id)
    if unclassified:
        stmt = stmt.where(
            Transaction.is_manual == False,
            Transaction.applied_rule_id == None
        )
    if description: stmt = stmt.where(Transaction.description.ilike(f"%{description}%"))
    transactions = db.execute(stmt).scalars().all()
    return list(transactions)

def get_by_id(db: Session, transaction_id: uuid.UUID) -> Transaction | None:
    transaction = db.execute(select(Transaction).where(Transaction.id == transaction_id)).scalars().first()
    return transaction

def create(db: Session, data: TransactionCreate) -> Transaction:
    db_transaction = Transaction(**data.model_dump())
    db.add(db_transaction)
    db.flush()
    db.refresh(db_transaction)
    return db_transaction

def delete(db: Session, transaction: Transaction):
    db.delete(transaction)

def update(db: Session, transaction: Transaction, data: TransactionUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)
    db.flush()
    db.refresh(transaction)
    return transaction
