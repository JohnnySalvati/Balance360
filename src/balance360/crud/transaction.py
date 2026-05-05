import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from balance360.models.transaction import Transaction
from balance360.schemas.transaction import TransactionCreate, TransactionUpdate

def get_all(db: Session) -> list[Transaction]:
    transactions = db.execute(select(Transaction)).scalars().all()
    return list(transactions)

def get_by_id(db: Session, transaction_id: uuid.UUID) -> Transaction | None:
    transaction = db.execute(select(Transaction).where(Transaction.id == transaction_id)).scalars().first()
    return transaction

def create(db: Session, data: TransactionCreate) -> Transaction:
    db_transaction = Transaction(**data.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def delete(db: Session, transaction: Transaction):
    db.delete(transaction)
    db.commit()

def update(db: Session, transaction: Transaction, data: TransactionUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)
    db.commit()
    db.refresh(transaction)
    return transaction
