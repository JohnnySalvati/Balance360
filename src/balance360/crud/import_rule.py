from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.import_rule import ImportRule
from balance360.schemas.import_rule import ImportRuleCreate, ImportRuleUpdate
from balance360.matching import find_best_rule
from balance360.enums import TransactionType

def get_all(db: Session) -> list[ImportRule]:
    import_rules = db.execute(select(ImportRule).order_by(ImportRule.pattern)).scalars().all()
    return list(import_rules)

def get_by_id(db: Session, import_rule_id:UUID) ->ImportRule|None:
    return db.execute(select(ImportRule).where(ImportRule.id == import_rule_id)).scalars().first()

def get_by_pattern(db: Session, pattern: str, transaction_type: TransactionType) -> ImportRule|None:
    import_rules = get_all(db)
    import_rule = find_best_rule(pattern, transaction_type, import_rules)
    return import_rule

def create(db: Session, data: ImportRuleCreate) -> ImportRule:
    import_rule = ImportRule(**data.model_dump())
    db.add(import_rule)
    db.commit()
    db.refresh(import_rule)
    return import_rule

def update(db: Session, data: ImportRuleUpdate, import_rule: ImportRule) -> ImportRule:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(import_rule, field, value)
    db.commit()
    db.refresh(import_rule)
    return import_rule

def get_by_exact_pattern(db: Session, description: str, transaction_type: TransactionType) -> ImportRule | None:
    pattern = description.lower()
    stmt = select(ImportRule).where(
        ImportRule.pattern == pattern,
        ImportRule.transaction_type == transaction_type
    )
    return db.execute(stmt).scalars().first()

def delete(db: Session, import_rule: ImportRule):
    db.delete(import_rule)
    db.commit()
