import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from balance360.crud.account import create, delete, get_all, get_by_id, update
from balance360.dependencies import get_db
from balance360.models.account import Account
from balance360.schemas.account import AccountCreate, AccountRead, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


def get_account_or_404(account_id: uuid.UUID, db: Session = Depends(get_db)):
    account = get_by_id(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("/", response_model=list[AccountRead])
def list_accounts(db: Session = Depends(get_db)):
    return get_all(db)


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account: Account = Depends(get_account_or_404)):
    return account


@router.post("/", response_model=AccountRead)
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    return create(db, data)


@router.delete("/{account_id}", status_code=204)
def delete_account(account: Account = Depends(get_account_or_404), db: Session = Depends(get_db)):
    delete(db, account)


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    data: AccountUpdate,
    account: Account = Depends(get_account_or_404),
    db: Session = Depends(get_db),
):
    return update(db, account, data)
