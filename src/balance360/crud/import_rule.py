from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.import_rule import ImportRule
from balance360.schemas.import_rule import ImportRuleCreate, ImportRuleUpdate

def get_all(db: Session) -> list[ImportRule]:
    import_rules = db.execute(select(ImportRule)).scalars().all()
    return list(import_rules)

def get_by_pattern(db: Session, pattern: str) -> ImportRule|None:
    import_rule = db.execute(select(ImportRule).where(ImportRule.pattern == pattern.lower())).scalars().first()
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