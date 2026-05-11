import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from balance360.enums import TransactionType
from balance360.models.transaction import Transaction
from balance360.schemas.transaction import TransactionRead, TransactionCreate, TransactionUpdate
from balance360.crud.transaction import get_all, get_by_id, create, delete, update
from balance360.dependencies import get_db

router = APIRouter(prefix="/transactions", tags=["transactions"])

def get_transaction_or_404(transaction_id: uuid.UUID, db: Session = Depends(get_db)):
    transaction = get_by_id(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction

@router.get("/", response_model=list[TransactionRead])
def list_transactions(
    date_from: date|None = None,
    date_to: date|None = None,
    entity_id: uuid.UUID|None = None,
    account_id: uuid.UUID|None = None,
    transaction_type: TransactionType|None = None,
    category_id: uuid.UUID|None = None,
    db: Session = Depends(get_db)):
    return get_all(
        date_from=date_from,
        date_to=date_to,
        entity_id=entity_id,
        account_id=account_id,
        transaction_type=transaction_type,
        category_id=category_id,
        db=db)

@router.get("/{transaction_id}", response_model=TransactionRead)
def get_transaction(transaction: Transaction = Depends(get_transaction_or_404)):
    return transaction

@router.post("/", response_model=TransactionRead)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    return create(db, data)

@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction: Transaction = Depends(get_transaction_or_404), db: Session = Depends(get_db)):
    delete(db, transaction)

@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_transaction(data: TransactionUpdate, transaction: Transaction = Depends(get_transaction_or_404), db: Session = Depends(get_db)):
    return update(db, transaction, data)