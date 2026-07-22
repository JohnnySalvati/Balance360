import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.models.account import Account
from balance360.schemas.account import AccountCreate, AccountUpdate


def get_all(db: Session, search: str | None = None) -> list[Account]:

    stmt = select(Account)

    if search:
        stmt = stmt.where(Account.name.ilike(f"%{search}%"))

    accounts = db.execute(stmt.order_by(Account.name)).scalars().all()

    return list(accounts)


def get_by_id(db: Session, account_id: uuid.UUID) -> Account | None:
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
    db.flush()


def update(db: Session, account: Account, data: AccountUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.flush()
    db.refresh(account)
    return account
