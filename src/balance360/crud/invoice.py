import uuid
from datetime import date

from sqlalchemy import select, true
from sqlalchemy.orm import Session

from balance360.enums import InvoiceType
from balance360.models.invoice import Invoice
from balance360.schemas.invoice import InvoiceCreate, InvoiceUpdate


def get_all(
    db: Session,
    invoice_type: InvoiceType | None = None,
    start: date | None = None,
    end: date | None = None,
    entity_ids: list[uuid.UUID] | None = [],
) -> list[Invoice]:

    entity_filter = Invoice.entity_id.in_(entity_ids) if entity_ids is not None else true()

    stmt = select(Invoice).where(entity_filter).where(Invoice.date.between(start, end))

    if invoice_type:
        stmt = stmt.where(Invoice.invoice_type == invoice_type)

    stmt = stmt.order_by(Invoice.date)

    invoices = db.execute(stmt).scalars().all()
    return list(invoices)


def get_by_id(db: Session, invoice_id: uuid.UUID) -> Invoice | None:
    return db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalars().first()


def create(db: Session, data: InvoiceCreate) -> Invoice:
    invoice = Invoice(**data.model_dump())
    db.add(invoice)
    db.flush()
    db.refresh(invoice)
    return invoice


def update(db: Session, data: InvoiceUpdate, invoice: Invoice) -> Invoice:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)

    if invoice.formal:
        if not invoice.pos:
            raise ValueError("Se necesita punto de venta")
        if invoice.invoice_type == InvoiceType.purchase and not invoice.number:
            raise ValueError("Se necesita numero de comprobante")

    db.flush()
    db.refresh(invoice)
    return invoice


def delete(db: Session, invoice: Invoice):
    db.delete(invoice)
    db.flush()
