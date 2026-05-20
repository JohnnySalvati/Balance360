import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.invoice import Invoice
from balance360.schemas.invoice import InvoiceCreate, InvoiceUpdate
from balance360.enums import VoucherStatus

def get_all(db: Session) -> list[Invoice]:
    invoices = db.execute(select(Invoice)).scalars().all()
    return list(invoices)

def get_by_id(db: Session, invoice_id: uuid.UUID) -> Invoice|None:
    return db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalars().first()

def create(db: Session, data: InvoiceCreate) -> Invoice:
    invoice = Invoice(**data.model_dump(), status = VoucherStatus.draft)
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice

def update(db: Session, data: InvoiceUpdate, invoice: Invoice) -> Invoice:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)
    if invoice.formal:
        if not(invoice.voucher_type and invoice.pos and invoice.number):
            raise ValueError("Todos los atributos son requeridos") 
    db.commit()
    db.refresh(invoice)
    return invoice

def delete(db: Session, invoice: Invoice):
    db.delete(invoice)
    db.commit()

