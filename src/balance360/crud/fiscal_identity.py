import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.models.fiscal_identity import FiscalIdentity
from balance360.schemas.fiscal_identity import FiscalIdentityCreate, FiscalIdentityUpdate


def get_all(db: Session) -> list[FiscalIdentity]:
    fiscal_identities = db.execute(select(FiscalIdentity)).scalars().all()
    return list(fiscal_identities)


def get_by_id(db: Session, fiscal_identity_id: uuid.UUID) -> FiscalIdentity | None:
    return db.get(FiscalIdentity, fiscal_identity_id)


def create(db: Session, data: FiscalIdentityCreate) -> FiscalIdentity:
    db_fiscal_identity = FiscalIdentity(**data.model_dump())
    db.add(db_fiscal_identity)
    db.flush()
    db.refresh(db_fiscal_identity)
    return db_fiscal_identity


def delete(db: Session, fiscal_identity: FiscalIdentity):
    db.delete(fiscal_identity)
    db.flush()


def update(db: Session, fiscal_identity: FiscalIdentity, data: FiscalIdentityUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(fiscal_identity, field, value)
    db.flush()
    db.refresh(fiscal_identity)
    return fiscal_identity


def get_by_ids(db: Session, fiscal_identity_ids: list[uuid.UUID]) -> list[FiscalIdentity]:
    fiscal_identities = (
        db.execute(select(FiscalIdentity).where(FiscalIdentity.id.in_(fiscal_identity_ids)))
        .scalars()
        .all()
    )
    return list(fiscal_identities)
