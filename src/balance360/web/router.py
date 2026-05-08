from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Query, Form, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.crud import transaction as transaction_crud
from balance360.crud import entity as entity_crud
from balance360.crud import contact as contact_crud
from balance360.crud import category as category_crud

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / 'templates')
def format_amount(value):
    return f"{value:,.2f}"

templates.env.filters["amount"] = format_amount

@router.get("/transactions")
def transaction_list(request: Request, db: Session = Depends(get_db)):
    transactions = transaction_crud.get_all(db)
    entities = entity_crud.get_all(db)
    contacts = contact_crud.get_all(db)
    categories = category_crud.get_all(db)

    return templates.TemplateResponse(
        request=request,
        name="transactions/list.html",
        context={
            "transactions": transactions,
            "entities": entities,
            "contacts": contacts,
            "categories": categories
            }
    )

@router.get("/transactions/rows")
def transaction_rows(
    request: Request,
    db: Session = Depends(get_db),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    transaction_type: str = Query(default="")
):
    from datetime import date
    from balance360.enums import TransactionType

    date_from_parsed = date.fromisoformat(date_from) if date_from else None
    date_to_parsed = date.fromisoformat(date_to) if date_to else None
    type_parsed = TransactionType(transaction_type) if transaction_type else None

    transactions = transaction_crud.get_all(
        db,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
        transaction_type=type_parsed
    )
    return templates.TemplateResponse(
        request=request,
        name="transactions/rows.html",
        context={"transactions": transactions}
    )

@router.patch("/transactions/{transaction_id}/classify")
def classify_transaction(
    request: Request,
    transaction_id: UUID,
    db: Session = Depends(get_db),
    entity_id:  UUID | None = Form(default=None),
    contact_id: UUID | None = Form(default=None),
    category_id: UUID | None = Form(default=None),
    create_rule: bool = Form(default=True)
    ):

    from balance360.schemas.transaction import TransactionUpdate
    from balance360.crud import import_rule as import_rule_crud
    from balance360.schemas.import_rule import ImportRuleUpdate, ImportRuleCreate

    transaction = transaction_crud.get_by_id(db, transaction_id)
    if not transaction: raise HTTPException(status_code=404, detail="Transaction not found")
    entities = entity_crud.get_all(db)
    contacts = contact_crud.get_all(db)
    categories = category_crud.get_all(db)

    transaction_data = TransactionUpdate(
        entity_id = entity_id, 
        contact_id = contact_id,
        category_id = category_id,
        is_manual = True
    )
    transaction = transaction_crud.update(db=db, transaction=transaction, data=transaction_data)
    imported_rule = None

    if create_rule:
        rule = import_rule_crud.get_by_pattern(db, transaction.description)
        if rule:
            import_rule_data = ImportRuleUpdate(
                entity_id = entity_id, 
                contact_id = contact_id,
                category_id = category_id,
            )
            import_rule_crud.update(db, data=import_rule_data, import_rule=rule)
        else:
            import_rule_data = ImportRuleCreate(
                pattern = transaction.description.lower(),
                entity_id = entity_id, 
                contact_id = contact_id,
                category_id = category_id
            )
            import_rule_crud.create(db, data=import_rule_data)

    return templates.TemplateResponse(
        request=request,
        name="transactions/row.html",
        context={
            "t": transaction, 
            "entities": entities,
            "contacts": contacts,
            "categories": categories
        }
    )


