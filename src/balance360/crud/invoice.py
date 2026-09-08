import uuid
from datetime import date

from sqlalchemy import exists, select, true
from sqlalchemy.orm import Session, aliased, joinedload, selectinload

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
    stmt = stmt.options(
        joinedload(Invoice.entity),
        joinedload(Invoice.contact),
        joinedload(Invoice.category),
        joinedload(Invoice.fiscal_identity),
        selectinload(Invoice.invoice_lines),
        selectinload(Invoice.invoice_tributes),
    )

    invoices = db.execute(stmt).scalars().all()
    return list(invoices)


def get_pending_fulfillment(
    db: Session, entity_ids: list[uuid.UUID] | None = None
) -> list[Invoice]:
    """Comprobantes confirmados cuya mercaderia todavia no se movio.

    Es la red que sostiene todo lo demas: separar el hecho fiscal del fisico solo es
    seguro si hay una pantalla que muestre lo que quedo colgado. Sin esto, una venta
    facturada y no entregada no se distingue de una entregada hasta que el stock no
    cierra, meses despues.

    Los anulados por una NC confirmada no cuentan: esos ya no se van a entregar nunca.
    """
    annulling_nc = aliased(Invoice)
    annulled = exists().where(annulling_nc.related_invoice_id == Invoice.id, annulling_nc.confirmed)

    stmt = (
        select(Invoice)
        .where(Invoice.confirmed)
        .where(Invoice.fulfilled_at.is_(None))
        .where(~annulled)
        .order_by(Invoice.date)
        .options(
            joinedload(Invoice.entity),
            joinedload(Invoice.contact),
            selectinload(Invoice.invoice_lines),
        )
    )

    if entity_ids is not None:
        stmt = stmt.where(Invoice.entity_id.in_(entity_ids))

    return list(db.execute(stmt).scalars().all())


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
    db.flush()
    db.refresh(invoice)
    return invoice


def delete(db: Session, invoice: Invoice):
    db.delete(invoice)
    db.flush()
