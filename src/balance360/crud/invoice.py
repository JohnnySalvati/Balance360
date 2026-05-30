import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.invoice import Invoice
from balance360.schemas.invoice import InvoiceCreate, InvoiceUpdate
from balance360.enums import InvoiceType

def get_all(db: Session, invoice_type: InvoiceType|None=None) -> list[Invoice]:
    q = select(Invoice)
    if invoice_type:
        q = q.where(Invoice.invoice_type == invoice_type)
    invoices = db.execute(q).scalars().all()
    return list(invoices)

def get_by_id(db: Session, invoice_id: uuid.UUID) -> Invoice|None:
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

