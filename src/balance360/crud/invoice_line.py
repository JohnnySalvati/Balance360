import uuid
from sqlalchemy import Select
from sqlalchemy.orm import Session
from balance360.models.invoice_line import InvoiceLine
from balance360.schemas.invoice_line import InvoiceLineCreate, InvoiceLineUpdate

def get_all(db: Session) -> list[InvoiceLine]:
    invoice_lines = db.execute(Select(InvoiceLine)).scalars().all()
    return list(invoice_lines)

def get_by_id(db: Session, invoice_line_id: uuid.UUID) -> InvoiceLine|None:
    return db.execute(Select(InvoiceLine).where(InvoiceLine.id == invoice_line_id)).scalars().first()

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

