from uuid import UUID
from pathlib import Path
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Query, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.crud import import_rule as import_rule_crud
from balance360.crud import transaction as transaction_crud
from balance360.crud import entity as entity_crud
from balance360.crud import contact as contact_crud
from balance360.crud import category as category_crud
from balance360.crud import account as account_crud
from balance360.schemas.transaction import TransactionUpdate, TransactionCreate
from balance360.schemas.import_rule import ImportRuleUpdate, ImportRuleCreate
from balance360.models.transaction import Transaction
from balance360.enums import TransactionType

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def format_amount(value):
    return f"{value:,.2f}"


templates.env.filters["amount"] = format_amount


@router.get("/transactions")
def transaction_list(request: Request, db: Session = Depends(get_db)):
    transactions = transaction_crud.get_all(db)
    entities = entity_crud.get_all(db)
    contacts = contact_crud.get_all(db)
    categories = category_crud.get_all(db)
    accounts = account_crud.get_all(db)

    return templates.TemplateResponse(
        request=request,
        name="transactions/list.html",
        context={
            "transactions": transactions,
            "total_count": len(transactions),
            "entities": entities,
            "contacts": contacts,
            "categories": categories,
            "accounts": accounts,
        },
    )


@router.get("/transactions/rows")
def transaction_rows(
    request: Request,
    db: Session = Depends(get_db),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    transaction_type: str = Query(default=""),
    account_id: str = Query(default=""),
    unclassified: str = Query(default=""),
    description: str = Query(default=""),
    entity_id: str = Query(default=""),
    category_id: str = Query(default=""),
):

    date_from_parsed = date.fromisoformat(date_from) if date_from else None
    date_to_parsed = date.fromisoformat(date_to) if date_to else None
    type_parsed = TransactionType(transaction_type) if transaction_type else None
    account_id_parsed = UUID(account_id) if account_id else None
    unclassified_parsed = unclassified == "true"
    entity_id_parsed = UUID(entity_id) if entity_id else None
    category_id_parsed = UUID(category_id) if category_id else None

    transactions = transaction_crud.get_all(
        db,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
        transaction_type=type_parsed,
        account_id=account_id_parsed,
        unclassified=unclassified_parsed,
        description=description,
        entity_id=entity_id_parsed,
        category_id=category_id_parsed,
    )

    total_count = db.scalar(select(func.count()).select_from(Transaction))
    return templates.TemplateResponse(
        request=request,
        name="transactions/rows.html",
        context={
            "transactions": transactions,
            "total_count": total_count,
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "accounts": account_crud.get_all(db),
        },
    )


@router.get("/transactions/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')


@router.get("/transactions/new-form")
def new_transaction_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="transactions/_form_modal.html",
        context={
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "accounts": account_crud.get_all(db),
        },
    )


@router.post("/transactions/create")
def create_transaction(
    request: Request,
    db: Session = Depends(get_db),
    transaction_date: str = Form(...),
    description: str = Form(...),
    amount: str = Form(...),
    transaction_type: str = Form(...),
    account_id: str = Form(...),
    entity_id: str = Form(default=""),
    contact_id: str = Form(default=""),
    category_id: str = Form(default=""),
    is_transfer: bool = Form(default=False),
):

    data = TransactionCreate(
        date=date.fromisoformat(transaction_date),
        description=description,
        amount=Decimal(amount),
        type=TransactionType(transaction_type),
        account_id=UUID(account_id),
        entity_id=UUID(entity_id) if entity_id else None,
        contact_id=UUID(contact_id) if contact_id else None,
        category_id=UUID(category_id) if category_id else None,
        is_manual=True,
        is_transfer=is_transfer,
    )
    transaction_crud.create(db, data)

    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response

@router.patch("/transactions/{transaction_id}/classify")
def classify_transaction(
    request: Request,
    transaction_id: UUID,
    db: Session = Depends(get_db),
    entity_id: UUID | None = Form(default=None),
    contact_id: UUID | None = Form(default=None),
    category_id: UUID | None = Form(default=None),
    create_rule: bool = Form(default=True),
    is_transfer: bool = Form(default=False),
):
    transaction = transaction_crud.get_by_id(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    entities = entity_crud.get_all(db)
    contacts = contact_crud.get_all(db)
    categories = category_crud.get_all(db)

    transaction_data = TransactionUpdate(
        entity_id=entity_id,
        contact_id=contact_id,
        category_id=category_id,
        is_manual=True,
        is_transfer=is_transfer,
    )
    transaction = transaction_crud.update(db=db, transaction=transaction, data=transaction_data)

    if create_rule:
        rule = import_rule_crud.get_by_exact_pattern(db, transaction.description, transaction.type)
        if rule:
            import_rule_data = ImportRuleUpdate(
                entity_id=entity_id,
                contact_id=contact_id,
                category_id=category_id,
                transaction_type=transaction.type,
                is_transfer=is_transfer,
            )
            import_rule = import_rule_crud.update(db, data=import_rule_data, import_rule=rule)
        else:
            import_rule_data = ImportRuleCreate(
                pattern=transaction.description.lower(),
                entity_id=entity_id,
                contact_id=contact_id,
                category_id=category_id,
                transaction_type=transaction.type,
                is_transfer=is_transfer,
            )
            import_rule = import_rule_crud.create(db, data=import_rule_data)
        transaction_data = TransactionUpdate(applied_rule_id=import_rule.id)
        transaction = transaction_crud.update(db=db, transaction=transaction, data=transaction_data)

    return templates.TemplateResponse(
        request=request,
        name="transactions/row.html",
        context={
            "t": transaction,
            "entities": entities,
            "contacts": contacts,
            "categories": categories,
        },
    )

@router.post("/transactions/apply-rules")
def apply_rules(
    request: Request,
    db: Session = Depends(get_db),
    date_from: str = Form(default=""),
    date_to: str = Form(default=""),
    transaction_type: str = Form(default=""),
    account_id: str = Form(default=""),
    unclassified: str = Form(default=""),
    description: str = Form(default=""),
    entity_id: str = Form(default=""),
    category_id: str = Form(default=""),
):
    from balance360.matching import find_best_rule

    all_transactions = [t for t in transaction_crud.get_all(db) if not t.is_manual]
    import_rules = import_rule_crud.get_all(db)
    for transaction in all_transactions:
        import_rule = find_best_rule(transaction.description, transaction.type, import_rules)
        if import_rule:
            transaction_data = TransactionUpdate(
                entity_id=import_rule.entity_id,
                contact_id=import_rule.contact_id,
                category_id=import_rule.category_id,
                is_transfer=import_rule.is_transfer,
                applied_rule_id=import_rule.id,
            )
            for field, value in transaction_data.model_dump(exclude_unset=True).items():
                setattr(transaction, field, value)
    db.flush()

    date_from_parsed = date.fromisoformat(date_from) if date_from else None
    date_to_parsed = date.fromisoformat(date_to) if date_to else None
    type_parsed = TransactionType(transaction_type) if transaction_type else None
    account_id_parsed = UUID(account_id) if account_id else None
    unclassified_parsed = unclassified == "true"
    entity_id_parsed = UUID(entity_id) if entity_id else None
    category_id_parsed = UUID(category_id) if category_id else None

    filtered = transaction_crud.get_all(
        db,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
        transaction_type=type_parsed,
        account_id=account_id_parsed,
        unclassified=unclassified_parsed,
        description=description,
        entity_id=entity_id_parsed,
        category_id=category_id_parsed,
    )
    return templates.TemplateResponse(
        request=request,
        name="transactions/rows.html",
        context={
            "transactions": filtered,
            "total_count": len(transaction_crud.get_all(db)),
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "accounts": account_crud.get_all(db),
        },
    )

@router.get("/transactions/{transaction_id}/edit-form")
def transaction_edit_form(request: Request, transaction_id: UUID, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="transactions/_form_modal.html",
        context={
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "accounts": account_crud.get_all(db),
            "transaction": transaction_crud.get_by_id(db, transaction_id)
        }
    )

@router.delete("/transactions/{transaction_id}")
def transaction_delete(transaction_id: UUID, db: Session = Depends(get_db)):
    transaction = transaction_crud.get_by_id(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    transaction_crud.delete(db, transaction)
    return HTMLResponse("")

@router.patch("/transactions/{transaction_id}/update")
def transaction_update(
    request: Request,
    transaction_id: UUID,
    db: Session = Depends(get_db),
    transaction_date: str = Form(...),
    description: str = Form(...),
    amount: str = Form(...),
    transaction_type: str = Form(...),
    account_id: str = Form(...),
    entity_id: str = Form(default=""),
    contact_id: str = Form(default=""),
    category_id: str = Form(default=""),
    is_manual: bool = Form(default=True),
    is_transfer: bool = Form(default=False),
    applied_rule_id: str= Form(default="")
    ):

    date_parsed = date.fromisoformat(transaction_date) if transaction_date else None
    amount_parsed = Decimal(amount)
    transaction_type_parsed = TransactionType(transaction_type)
    account_id_parsed = UUID(account_id)
    entity_id_parsed = UUID(entity_id) if entity_id else None
    contact_id_parsed = UUID(contact_id) if contact_id else None
    category_id_parsed = UUID(category_id) if category_id else None
    applied_rule_id_parsed = UUID(applied_rule_id) if applied_rule_id else None

    transaction = transaction_crud.get_by_id(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    data = TransactionUpdate(
        date=date_parsed,
        description=description,
        amount=amount_parsed,
        type=transaction_type_parsed,
        account_id=account_id_parsed,
        entity_id=entity_id_parsed,
        contact_id=contact_id_parsed,
        category_id=category_id_parsed,
        is_manual=is_manual,
        is_transfer=is_transfer,
        applied_rule_id=applied_rule_id_parsed
    )

    transaction_crud.update(
        db=db,
        transaction=transaction,
        data=data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response