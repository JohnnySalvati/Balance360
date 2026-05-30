import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from balance360.schemas.account import AccountCreate, AccountUpdate
from balance360.models.account import Account

def get_all(db: Session) -> list[Account]:
    accounts = db.execute(select(Account)).scalars().all()
    return list(accounts)

def get_by_id(db: Session, account_id: uuid.UUID) -> Account|None:
    account = db.execute(select(Account).where(Account.id == account_id)).scalars().first()
    return account

def create(db: Session, data: AccountCreate) -> Account:
    db_account = Account(**data.model_dump())
    db.add(db_account)
    db.flush()
    db.refresh(db_account)
    return db_account

def delete(db: Session, account: Account):
    db.delete(account)

def update(db: Session, account: Account, data: AccountUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.flush()
    db.refresh(account)
    return account
