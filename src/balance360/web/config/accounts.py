import uuid
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from balance360.dependencies import get_db
from balance360.enums import AccountType
from balance360.crud import account as account_crud
from balance360.crud import currency as currency_crud
from balance360.schemas.account import AccountCreate, AccountUpdate

router = APIRouter(prefix="/accounts")
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

@router.get("/", response_class=HTMLResponse)
def accounts_page(request: Request, db: Session = Depends(get_db)):
    accounts = account_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="config/accounts/list.html",
        context={"accounts": accounts}
    )

@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')

@router.get("/rows")
def accounts_rows(request: Request, db: Session = Depends(get_db)):
    accounts = account_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="config/accounts/_rows.html",
        context={"accounts": accounts}
    )

@router.get("/new-form")
def new_account_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="config/accounts/_form_modal.html",
        context={
            "accounts": account_crud.get_all(db),
            "account_type": AccountType,
            "currencies": currency_crud.get_all(db)
            }
    )

@router.post("/", response_class=HTMLResponse)
def create_account(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    account_type: str = Form(...),
    currency_id: str = Form(...)
):
    data = AccountCreate(
        name=name,
        type=AccountType(account_type),
        currency_id=uuid.UUID(currency_id)
    )
    account_crud.create(db, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response

@router.get("/{account_id}/edit-form")
def account_edit_form(
    request: Request,
    account_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        request=request,
        name="config/accounts/_form_modal.html",
        context={
            "account": account_crud.get_by_id(db, account_id),
            "account_type": AccountType,
            "currencies": currency_crud.get_all(db)
        }
    )

@router.patch("/{account_id}", response_class=HTMLResponse)
def update_account(
    request: Request,
    account_id: uuid.UUID,
    db: Session= Depends(get_db),
    name: str = Form(...),
    account_type: str = Form(...),
    currency_id: str = Form(...)
):
    account = account_crud.get_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    data = AccountUpdate(
        name=name,
        type=AccountType(account_type),
        currency_id=uuid.UUID(currency_id)
    )
    account_crud.update(db, account, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response

@router.delete("/{account_id}", response_class=HTMLResponse)
def delete_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    account = account_crud.get_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.transactions:
        return HTMLResponse(
            '<tr><td colspan="4" class="px-4 py-2 text-red-600 text-sm">'
            f'No se puede eliminar "{account.name}": tiene transacciones asociadas.'
            '</td></tr>'
        )
    account_crud.delete(db, account)
    return HTMLResponse("")