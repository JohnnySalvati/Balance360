import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from balance360.models.invoice_line import InvoiceLine
from balance360.models.serial_number import SerialNumber
from balance360.crud import invoice_line as invoice_line_crud
from balance360.enums import InvoiceType
from balance360.schemas.serial_number import SerialNumberCreate

def get_by_invoice_line_id(db: Session, invoice_line_id: uuid.UUID) -> list[SerialNumber]:
    
    invoice_line = invoice_line_crud.get_by_id(db, invoice_line_id)

    assert invoice_line
    if invoice_line.invoice.invoice_type == InvoiceType.purchase:
        serial_numbers = db.execute(select(SerialNumber).where(SerialNumber.purchase_line_id == invoice_line_id)).scalars().all()
    else:
        serial_numbers = db.execute(select(SerialNumber).where(SerialNumber.sale_line_id == invoice_line_id)).scalars().all()

    return list(serial_numbers)

def get_by_id(db: Session, id: uuid.UUID) -> SerialNumber|None:
    return db.execute(select(SerialNumber).where(SerialNumber.id == id)).scalars().first()

def get_by_serial(db: Session, serial: str) -> SerialNumber|None:
    return db.execute(select(SerialNumber).where(SerialNumber.serial == serial)).scalars().first()


def create(db: Session, data: SerialNumberCreate) -> SerialNumber:
    serial_number = SerialNumber(**data.model_dump())
    db.add(serial_number)
    db.flush()
    db.refresh(serial_number)
    return serial_number

def delete(db:Session, serial_number: SerialNumber):
    db.delete(serial_number)
    