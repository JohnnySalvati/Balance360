import uuid

from sqlalchemy import Select
from sqlalchemy.orm import Session

from balance360.models.invoice_tribute import InvoiceTribute
from balance360.schemas.invoice_tribute import InvoiceTributeCreate


def get_by_id(db: Session, tribute_id: uuid.UUID) -> InvoiceTribute | None:
    return (
        db.execute(Select(InvoiceTribute).where(InvoiceTribute.id == tribute_id)).scalars().first()
    )


def create(db: Session, data: InvoiceTributeCreate) -> InvoiceTribute:
    tribute = InvoiceTribute(**data.model_dump())
    db.add(tribute)
    db.flush()
    db.refresh(tribute)
    return tribute


def delete(db: Session, tribute: InvoiceTribute):
    db.delete(tribute)
    db.flush()
