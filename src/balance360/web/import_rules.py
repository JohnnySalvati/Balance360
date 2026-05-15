import uuid
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from balance360.enums import TransactionType
from balance360.dependencies import get_db
from balance360.crud import import_rule as import_rule_crud
from balance360.crud import entity as entity_crud
from balance360.crud import contact as contact_crud
from balance360.crud import category as category_crud
from balance360.schemas.import_rule import ImportRuleCreate, ImportRuleUpdate

router = APIRouter(prefix="/import-rules")
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
def import_rules_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="import_rules/list.html",
        context={
            "import_rules": import_rule_crud.get_all(db),
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "transaction_types": TransactionType
            }
    )

@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')

@router.get("/rows")
def import_rules_rows(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="import_rules/_rows.html",
        context={
            "import_rules": import_rule_crud.get_all(db),
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "transaction_types": TransactionType
            }
    )

@router.get("/new-form")
def new_import_rule_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="import_rules/_form_modal.html",
        context={
            "import_rules": import_rule_crud.get_all(db),
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "transaction_types": TransactionType
            }
    )

@router.post("/", response_class=HTMLResponse)
def create_import_rule(
        request: Request,
        db: Session = Depends(get_db),
        pattern: str = Form(...),
        entity_id: str = Form(default=""),
        contact_id: str = Form(default=""),
        category_id: str = Form(default=""),
        transaction_type: str = Form(default=""),
        is_transfer: bool = Form(default=False)
):
    data = ImportRuleCreate(
        pattern=pattern,
        entity_id=uuid.UUID(entity_id) if entity_id else None,
        contact_id=uuid.UUID(contact_id) if contact_id else None,
        category_id=uuid.UUID(category_id) if category_id else None,
        transaction_type=TransactionType(transaction_type),
        is_transfer=is_transfer
    )
    import_rule_crud.create(db, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response

@router.get("/{import_rule_id}/edit-form")
def import_rule_edit_form(request: Request, import_rule_id: uuid.UUID, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="import_rules/_form_modal.html",
        context={
            "import_rule": import_rule_crud.get_by_id(db, import_rule_id),
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "transaction_types": TransactionType
        }
    )


@router.patch("/{import_rule_id}", response_class=HTMLResponse)
def update_import_rule(
        import_rule_id: uuid.UUID,
        db: Session = Depends(get_db),
        pattern: str = Form(default=""),
        entity_id: str = Form(default=""),
        contact_id: str = Form(default=""),
        category_id: str = Form(default=""),
        transaction_type: str = Form(default=""),
        is_transfer: bool = Form(default=False)
):
    import_rule = import_rule_crud.get_by_id(db, import_rule_id)
    if not import_rule:
        raise HTTPException(status_code=404, detail="Import Rule not found")
    data = ImportRuleUpdate(
        pattern=pattern if pattern else None,
        entity_id=uuid.UUID(entity_id) if entity_id else None,
        contact_id=uuid.UUID(contact_id) if contact_id else None,
        category_id=uuid.UUID(category_id) if category_id else None,
        transaction_type=TransactionType(transaction_type),
        is_transfer=is_transfer
    )
    import_rule_crud.update(db, data, import_rule)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response

@router.delete("/{import_rule_id}", response_class=HTMLResponse)
def delete_import_rule(
    import_rule_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    import_rule = import_rule_crud.get_by_id(db, import_rule_id)
    if not import_rule:
        raise HTTPException(status_code=404, detail="Category not found")
    import_rule_crud.delete(db, import_rule)
    return HTMLResponse("")
