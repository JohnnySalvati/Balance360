import uuid
from pathlib import Path
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.services import product as product_service
from balance360.crud import product as product_crud
from balance360.schemas.product import ProductCreate, ProductUpdate

router = APIRouter(prefix="/products")
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

@router.get("/", response_class=HTMLResponse)
def product_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="products/list.html",
        context={
            "products": product_crud.get_all(db)
        }
    )

@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')

@router.get("/rows")
def product_rows(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="products/_rows.html",
        context={
            "products": product_crud.get_all(db)
        }
    )

@router.get("/new-form")
def new_product_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="products/_form_modal.html",
        context={
            "products": product_crud.get_all(db)
        }
    )

@router.post("/", response_class=HTMLResponse)
def create_product(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    margin: str = Form(default=""),
    track_serial: bool = Form(default=False)
):
    data = ProductCreate(
        name=name,
        margin=Decimal(margin) if margin else Decimal(0),
        track_serial=track_serial
    )
    product_service.create_product(db, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response

@router.get("/{product_id}/edit-form")
def product_edit_form(request: Request, product_id: uuid.UUID, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="products/_form_modal.html",
        context={
            "product": product_crud.get_by_id(db, product_id)
        }
    )

@router.patch("/{product_id}", response_class=HTMLResponse)
def update_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    name: str|None = Form(default=""),
    margin: str|None = Form(default=""),
    track_serial: bool = Form(default=False)
):
    product = product_crud.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    data = ProductUpdate(
        name=name if name else None,
        margin=Decimal(margin) if margin else Decimal(0),
        track_serial=track_serial
    )
    product_service.update_product(db, product, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response

@router.delete("/{product_id}")
def delete_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    product = product_crud.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        product_service.delete_product(db, product)
    except product_service.ProductDeleteError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return HTMLResponse("")