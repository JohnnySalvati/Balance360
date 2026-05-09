from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Query, Form, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.crud import import_rule as import_rule_crud
from balance360.crud import transaction as transaction_crud
from balance360.crud import entity as entity_crud
from balance360.crud import contact as contact_crud
from balance360.crud import category as category_crud
from balance360.crud import account as account_crud
from balance360.schemas.transaction import TransactionUpdate
from balance360.schemas.import_rule import ImportRuleUpdate, ImportRuleCreate

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
            "accounts": accounts
            }
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
    description: str = Query(default="")
):
    from datetime import date
    from balance360.enums import TransactionType

    date_from_parsed = date.fromisoformat(date_from) if date_from else None
    date_to_parsed = date.fromisoformat(date_to) if date_to else None
    type_parsed = TransactionType(transaction_type) if transaction_type else None
    account_id_parsed = UUID(account_id) if account_id else None
    unclassified_parsed = unclassified == "true"
    
    transactions = transaction_crud.get_all(
        db,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
        transaction_type=type_parsed,
        account_id=account_id_parsed,
        unclassified=unclassified_parsed,
        description=description
    )
    total_count = len(transaction_crud.get_all(db))
    return templates.TemplateResponse(
        request=request,
        name="transactions/rows.html",
        context={
            "transactions": transactions,
            "total_count": total_count,
            "entities": entity_crud.get_all(db),
            "contacts": contact_crud.get_all(db),
            "categories": category_crud.get_all(db),
            "accounts": account_crud.get_all(db)
        }
    )

@router.patch("/transactions/{transaction_id}/classify")
def classify_transaction(
    request: Request,
    transaction_id: UUID,
    db: Session = Depends(get_db),
    entity_id:  UUID | None = Form(default=None),
    contact_id: UUID | None = Form(default=None),
    category_id: UUID | None = Form(default=None),
    create_rule: bool = Form(default=True),
    is_transfer: bool = Form(default=False)
    ):

    transaction = transaction_crud.get_by_id(db, transaction_id)
    if not transaction: raise HTTPException(status_code=404, detail="Transaction not found")
    entities = entity_crud.get_all(db)
    contacts = contact_crud.get_all(db)
    categories = category_crud.get_all(db)

    transaction_data = TransactionUpdate(
        entity_id = entity_id, 
        contact_id = contact_id,
        category_id = category_id,
        is_manual = True,
        is_transfer = is_transfer
    )
    transaction = transaction_crud.update(db=db, transaction=transaction, data=transaction_data)
    import_rule_data = None

    if create_rule:
        rule = import_rule_crud.get_by_pattern(db, transaction.description, transaction.type)
        if rule:
            import_rule_data = ImportRuleUpdate(
                entity_id = entity_id, 
                contact_id = contact_id,
                category_id = category_id,
                transaction_type = transaction.type,
                is_transfer = is_transfer
            )
            import_rule = import_rule_crud.update(db, data=import_rule_data, import_rule=rule)
        else:
            import_rule_data = ImportRuleCreate(
                pattern = transaction.description.lower(),
                entity_id = entity_id, 
                contact_id = contact_id,
                category_id = category_id,
                transaction_type = transaction.type,
                is_transfer = is_transfer
            )
            import_rule = import_rule_crud.create(db, data=import_rule_data)
        transaction_data = TransactionUpdate(
            applied_rule_id=import_rule.id
        )
        transaction = transaction_crud.update(db=db, transaction=transaction, data=transaction_data)

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

@router.post("/transactions/apply-rules")
def apply_rules(
    request: Request,
    db: Session = Depends(get_db),
    date_from: str = Form(default=""),
    date_to: str = Form(default=""),
    transaction_type: str = Form(default=""),
    account_id: str = Form(default=""),
    unclassified: str = Form(default=""),
    description: str = Form(default="")
):
    from datetime import date
    from balance360.enums import TransactionType
    from balance360.matching import find_best_rule

    all_transactions = [t for t in transaction_crud.get_all(db) if not t.is_manual]
    import_rules = import_rule_crud.get_all(db)
    for transaction in all_transactions:
        import_rule = find_best_rule(transaction.description, transaction.type, import_rules)
        if import_rule:
            transaction_data = TransactionUpdate(
                entity_id = import_rule.entity_id,
                contact_id = import_rule.contact_id,
                category_id = import_rule.category_id,
                is_transfer = import_rule.is_transfer,
                applied_rule_id = import_rule.id
            )
            for field, value in transaction_data.model_dump(exclude_unset=True).items():
                setattr(transaction, field, value)
    db.commit()

    date_from_parsed = date.fromisoformat(date_from) if date_from else None
    date_to_parsed = date.fromisoformat(date_to) if date_to else None
    type_parsed = TransactionType(transaction_type) if transaction_type else None
    account_id_parsed = UUID(account_id) if account_id else None
    unclassified_parsed = unclassified == "true"

    filtered = transaction_crud.get_all(
        db,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
        transaction_type=type_parsed,
        account_id=account_id_parsed,
        unclassified=unclassified_parsed,
        description=description
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
            "accounts": account_crud.get_all(db)
        }
    )

    

