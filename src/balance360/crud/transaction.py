import uuid
from datetime import date
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func
from balance360.enums import TransactionType, ClassificationStatus
from balance360.models.transaction import Transaction
from balance360.schemas.transaction import TransactionCreate, TransactionUpdate


def _apply_filters(
        stmt,
        date_from: date|None = None,
        date_to: date|None = None,
        entity_id: uuid.UUID|None = None,
        account_id: uuid.UUID|None = None,
        transaction_type: TransactionType|None = None,
        category_id: uuid.UUID|None = None,
        classification_status: ClassificationStatus|None = None,
        description: str = "",
):
    if date_from: stmt = stmt.where(Transaction.date >= date_from)
    if date_to: stmt = stmt.where(Transaction.date <= date_to)
    if entity_id: stmt = stmt.where(Transaction.entity_id == entity_id)
    if account_id: stmt = stmt.where(Transaction.account_id == account_id)
    if transaction_type: stmt = stmt.where(Transaction.type == transaction_type)
    if category_id: stmt = stmt.where(Transaction.category_id == category_id)
    if classification_status:
        match classification_status:
            case ClassificationStatus.unclassified:
                stmt = stmt.where(
                    Transaction.is_manual == False,
                    Transaction.applied_rule_id == None
                )
            case ClassificationStatus.auto_classified:
                stmt = stmt.where(
                    Transaction.is_manual == False,
                    Transaction.applied_rule_id != None
                )
            case ClassificationStatus.manual_no_rule:
                stmt = stmt.where(
                    Transaction.is_manual == True,
                    Transaction.applied_rule_id == None
                )
            case ClassificationStatus.manual_with_rule:
                stmt = stmt.where(
                    Transaction.is_manual == True,
                    Transaction.applied_rule_id != None
                )
    
    if description: stmt = stmt.where(Transaction.description.ilike(f"%{description}%"))
    return stmt


def get_all(
        db: Session,
        date_from: date|None = None,
        date_to: date|None = None,
        entity_id: uuid.UUID|None = None,
        account_id: uuid.UUID|None = None,
        transaction_type: TransactionType|None = None,
        category_id: uuid.UUID|None = None,
        classification_status: ClassificationStatus|None = None,
        description: str = "",
        limit: int|None = None,
        offset: int|None = 0
    ) -> list[Transaction]:

    stmt = select(Transaction)

    stmt = _apply_filters(
        stmt,
        date_from=date_from, 
        date_to=date_to,
        entity_id=entity_id,
        account_id=account_id,
        transaction_type=transaction_type,
        category_id=category_id,
        classification_status=classification_status,
        description=description
    )

    stmt = stmt.options(
            selectinload(Transaction.account),
            selectinload(Transaction.entity),
            selectinload(Transaction.contact),
            selectinload(Transaction.category),
        )
    
    stmt = stmt.order_by(Transaction.date, Transaction.id)

    if limit:
        stmt = stmt.limit(limit).offset(offset)

    transactions = db.execute(stmt).scalars().all()
    return list(transactions)

def count_all(
        db,
        date_from: date|None = None,
        date_to: date|None = None,
        entity_id: uuid.UUID|None = None,
        account_id: uuid.UUID|None = None,
        transaction_type: TransactionType|None = None,
        category_id: uuid.UUID|None = None,
        classification_status: ClassificationStatus|None = None,
        description: str = "",
    ) -> int:
    
    stmt = select(func.count()).select_from(Transaction)

    stmt = _apply_filters(
        stmt,
        date_from=date_from, 
        date_to=date_to,
        entity_id=entity_id,
        account_id=account_id,
        transaction_type=transaction_type,
        category_id=category_id,
        classification_status=classification_status,
        description=description
    )

    quantity = db.execute(stmt).scalar()
    return quantity

    

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
    db.flush()

def update(db: Session, transaction: Transaction, data: TransactionUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)
    db.flush()
    db.refresh(transaction)
    return transaction
