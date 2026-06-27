from sqlalchemy.orm import Session
from balance360.crud import serial_number as serial_number_crud
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.models.serial_number import SerialNumber
from balance360.schemas.serial_number import SerialNumberCreate, SerialNumberUpdate
from balance360.enums import InvoiceType, SerialStatus
from balance360.exceptions import SerialValidationError


def add_serial_to_line(db: Session, serial_str: str, invoice_line: InvoiceLine) -> SerialNumber:
    if not invoice_line.product_id:
        raise SerialValidationError("La línea no tiene producto asignado")

    serial_number = serial_number_crud.get_by_serial(db, serial_str)

    if invoice_line.invoice.invoice_type == InvoiceType.sale:
        _validate_for_sale(serial_number, invoice_line)
        serial_number_crud.update(db, serial_number, SerialNumberUpdate(  # type: ignore
            sale_line_id=invoice_line.id,
            status=SerialStatus.reserved
        ))
    else:
        _validate_for_purchase(serial_number, invoice_line)
        serial_number_crud.create(db, SerialNumberCreate(
            product_id=invoice_line.product_id,
            serial=serial_str,
            purchase_line_id=invoice_line.id,
            status=SerialStatus.pending
        ))

    db.refresh(invoice_line)
    return serial_number_crud.get_by_serial(db, serial_str)  # type: ignore


def remove_serial_from_line(db: Session, serial_number: SerialNumber, invoice_line: InvoiceLine) -> None:
    if invoice_line.invoice.invoice_type == InvoiceType.purchase:
        serial_number_crud.delete(db, serial_number)
    else:
        serial_number_crud.update(db, serial_number, SerialNumberUpdate(
            status=SerialStatus.available,
            sale_line_id=None
        ))
    db.flush()
    db.expire(invoice_line)


def _validate_for_sale(serial_number: SerialNumber | None, invoice_line: InvoiceLine) -> None:
    if not serial_number:
        raise SerialValidationError("Numero de serie inexistente")
    if serial_number.product_id != invoice_line.product_id:
        raise SerialValidationError("El numero de serie no corresponde al producto")
    if serial_number.status != SerialStatus.available:
        raise SerialValidationError("El serial no está disponible")
    if len(invoice_line.sold_serials) >= invoice_line.quantity:
        raise SerialValidationError("Cantidad de seriales excedida")


def _validate_for_purchase(serial_number: SerialNumber | None, invoice_line: InvoiceLine) -> None:
    if serial_number:
        raise SerialValidationError("Ya existe un serial con ese número")
    if len(invoice_line.purchased_serials) >= invoice_line.quantity:
        raise SerialValidationError("Cantidad de seriales excedida")
