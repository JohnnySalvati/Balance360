import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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
def list_transactions(db: Session = Depends(get_db)):
    return get_all(db)

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