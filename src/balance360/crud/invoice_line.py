import uuid

from sqlalchemy import Select
from sqlalchemy.orm import Session

from balance360.enums import InvoiceType
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.schemas.invoice_line import InvoiceLineCreate, InvoiceLineUpdate


def get_all(db: Session) -> list[InvoiceLine]:
    invoice_lines = db.execute(Select(InvoiceLine)).scalars().all()
    return list(invoice_lines)


def get_by_id(db: Session, invoice_line_id: uuid.UUID) -> InvoiceLine | None:
    return (
        db.execute(Select(InvoiceLine).where(InvoiceLine.id == invoice_line_id)).scalars().first()
    )


def get_by_invoice_product(
    db: Session, invoice_id: uuid.UUID, product_id: uuid.UUID
) -> InvoiceLine | None:
    return (
        db.execute(
            Select(InvoiceLine).where(
                InvoiceLine.invoice_id == invoice_id, InvoiceLine.product_id == product_id
            )
        )
        .scalars()
        .first()
    )


def get_by_last_product_purchase(
    db: Session, product_id: uuid.UUID, entity_id: uuid.UUID
) -> InvoiceLine | None:
    stmt = (
        Select(InvoiceLine)
        .where(
            Invoice.invoice_type == InvoiceType.purchase,
            Invoice.confirmed == True,
            Invoice.entity_id == entity_id,
        )
        .where(InvoiceLine.product_id == product_id)
        .join_from(InvoiceLine, Invoice)
        .order_by(Invoice.date.desc(), Invoice.created_at.desc())
    )
    return db.execute(stmt).scalars().first()


def create(db: Session, data: InvoiceLineCreate) -> InvoiceLine:
    invoice_line = InvoiceLine(**data.model_dump())
    db.add(invoice_line)
    db.flush()
    db.refresh(invoice_line)
    return invoice_line


def update(db: Session, data: InvoiceLineUpdate, invoice_line: InvoiceLine) -> InvoiceLine:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(invoice_line, field, value)
    db.flush()
    db.refresh(invoice_line)
    return invoice_line


def delete(db: Session, invoice_line: InvoiceLine):
    db.delete(invoice_line)
    db.flush()
