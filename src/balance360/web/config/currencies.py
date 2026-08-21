import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from balance360.crud import currency as currency_crud
from balance360.dependencies import get_db
from balance360.schemas.currency import CurrencyCreate, CurrencyUpdate
from balance360.web.templating import templates

router = APIRouter(prefix="/currencies")


def get_currency_or_404(currency_id: uuid.UUID, db: Session = Depends(get_db)):
    currency = currency_crud.get_by_id(db, currency_id)
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    return currency


@router.get("/", response_class=HTMLResponse, name="config_currencies")
def currency_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="currencies/list.html",
        context={"currencies": currency_crud.get_all(db)},
    )


@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')


@router.get("/rows")
def currency_rows(
    request: Request, search: str | None = Query(default=""), db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        request=request,
        name="currencies/_rows.html",
        context={"currencies": currency_crud.get_all(db, search)},
    )


@router.get("/new-form")
def new_currency_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="currencies/_form_modal.html",
        context={},
    )


@router.post("/", response_class=HTMLResponse)
def create_currency(
    db: Session = Depends(get_db),
    code: str = Form(...),
    name: str = Form(...),
    is_bond: bool = Form(default=False),
    is_index: bool = Form(default=False),
):
    currency_crud.create(
        db, CurrencyCreate(code=code.upper(), name=name, is_bond=is_bond, is_index=is_index)
    )
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.get("/{currency_id}/edit-form")
def currency_edit_form(request: Request, currency=Depends(get_currency_or_404)):
    return templates.TemplateResponse(
        request=request,
        name="currencies/_form_modal.html",
        context={"currency": currency},
    )


@router.patch("/{currency_id}", response_class=HTMLResponse)
def update_currency(
    currency=Depends(get_currency_or_404),
    db: Session = Depends(get_db),
    code: str | None = Form(default=""),
    name: str | None = Form(default=""),
    is_bond: bool = Form(default=False),
    is_index: bool = Form(default=False),
):
    data = CurrencyUpdate(
        code=code.upper() if code else None,
        name=name if name else None,
        is_bond=is_bond,
        is_index=is_index,
    )
    currency_crud.update(db, currency, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.delete("/{currency_id}", response_class=HTMLResponse)
def delete_currency(
    currency=Depends(get_currency_or_404),
    db: Session = Depends(get_db),
):
    currency_crud.delete(db, currency)

    return HTMLResponse("")
