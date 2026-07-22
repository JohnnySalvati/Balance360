from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.enums import TransactionType
from balance360.models.import_rule import ImportRule
from balance360.schemas.import_rule import ImportRuleCreate, ImportRuleUpdate


def get_all(db: Session, pattern: str = "") -> list[ImportRule]:
    stmt = select(ImportRule)

    if pattern:
        stmt = stmt.where(ImportRule.pattern.ilike(f"%{pattern}%"))

    stmt = stmt.order_by(ImportRule.pattern)

    import_rules = db.execute(stmt).scalars().all()
    return list(import_rules)


def get_by_id(db: Session, import_rule_id: UUID) -> ImportRule | None:
    return db.execute(select(ImportRule).where(ImportRule.id == import_rule_id)).scalars().first()


def create(db: Session, data: ImportRuleCreate) -> ImportRule:
    import_rule = ImportRule(**data.model_dump())
    db.add(import_rule)
    db.flush()
    db.refresh(import_rule)
    return import_rule


def update(db: Session, data: ImportRuleUpdate, import_rule: ImportRule) -> ImportRule:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(import_rule, field, value)
    db.flush()
    db.refresh(import_rule)
    return import_rule


def get_by_exact_pattern(
    db: Session, pattern: str, transaction_type: TransactionType
) -> list[ImportRule]:
    pattern_lower = pattern.lower()

    stmt = select(ImportRule).where(
        ImportRule.pattern == pattern_lower, ImportRule.transaction_type == transaction_type
    )

    stmt = stmt.order_by(ImportRule.pattern)

    import_rules = db.execute(stmt).scalars().all()
    return list(import_rules)


def delete(db: Session, import_rule: ImportRule):
    db.delete(import_rule)
    db.flush()
