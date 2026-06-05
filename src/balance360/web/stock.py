import uuid
from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from balance360.enums import SerialStatus
from balance360.dependencies import get_db
from balance360.crud import serial_number as serial_number_crud
from balance360.crud import product as product_crud
from balance360.models.serial_number import SerialNumber
from balance360.services.stock import get_stock_summary

router = APIRouter(prefix="/stock")
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/serials", response_class=HTMLResponse)
def serials_page(
    request: Request,
    db: Session = Depends(get_db),
    status: str|None = None,
    product_id: str|None = None,
    q: str|None = None
):
    status_parsed = SerialStatus(status) if status else None
    product_id_parsed = uuid.UUID(product_id) if product_id else None

    return templates.TemplateResponse(
        request=request,
        name="stock/serials.html",
        context={
            "serial_numbers": serial_number_crud.get_all(db, status_parsed, product_id_parsed, q),
            "statuses": SerialStatus,
            "products": product_crud.get_all(db),
            "current_status": status,
            "current_product_id": product_id,
            "current_q": q
            }
    )


def get_serial_number_or_404(
    serial_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SerialNumber:
    
    serial_number = serial_number_crud.get_by_id(db, serial_id)
    if not serial_number:
        raise HTTPException(status_code=404, detail="Serial number not found")
    return serial_number


@router.get("/serials/{serial_id}", response_class=HTMLResponse)
def serial_history(
    request: Request,
    serial_number: SerialNumber = Depends(get_serial_number_or_404)
):
    return templates.TemplateResponse(
        request=request,
        name="stock/serial_detail.html",
        context={
            "serial_number": serial_number,
            "product": serial_number.product,
            "purchase_date": serial_number.purchase_line.invoice.date,
            "supplier": serial_number.purchase_line.invoice.contact.name,
            "cost": serial_number.purchase_line.unit_price,
            "sale_date": serial_number.sale_line.invoice.date if serial_number.sale_line else None,
            "client": serial_number.sale_line.invoice.contact.name if serial_number.sale_line else None,
            "sale_price": serial_number.sale_line.unit_price if serial_number.sale_line else None
        }
    )


@router.get("/", response_class=HTMLResponse)
def stock(
    request: Request,
    db: Session = Depends(get_db)
):
    
    return templates.TemplateResponse(
        request=request,
        name="stock/index.html",
        context={"stock_items": get_stock_summary(db)}
    )