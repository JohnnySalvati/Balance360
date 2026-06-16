import uuid
import re
from decimal import Decimal, InvalidOperation
from rapidfuzz import process, fuzz
from sqlalchemy.orm import Session
from balance360.models.import_rule import ImportRule
from balance360.schemas.import_rule import ImportRuleCreate, ImportRuleUpdate
from balance360.crud import import_rule as import_rule_crud
from balance360.enums import TransactionType

class RuleConflictError(Exception):
    def __init__(self, pattern: str, count: int) -> None:
        self.pattern = pattern
        self.count = count

def extract_amount(description: str) -> Decimal | None:
    """Extract a monetary amount from a description string containing $ amounts."""
    match = re.search(r'\$\s*([\d.,]+)', description)
    if not match:
        return None
    raw = match.group(1)

    try:
        # Argentine format: dot thousands + comma decimal (e.g. 8.952,93)
        if re.match(r'^[\d.]+,\d{2}$', raw):
            normalized = raw.replace('.', '').replace(',', '.')

        # US format: has comma(s) (e.g. 68,461.96 or 1,156,611.23)
        elif ',' in raw:
            normalized = raw.replace(',', '')

        # Multiple dots — typo mixing separators (e.g. 25.883.75 → 25883.75)
        elif raw.count('.') > 1:
            parts = raw.rsplit('.', 1)
            normalized = parts[0].replace('.', '') + '.' + parts[1]

        # Single dot: distinguish thousands (15.800) from decimal (9196.59)
        elif '.' in raw:
            _, decimal_part = raw.split('.')
            normalized = raw.replace('.', '') if len(decimal_part) == 3 else raw

        else:
            normalized = raw

        return Decimal(normalized)

    except InvalidOperation:
        return None

def find_best_rule(pattern: str, transaction_type: TransactionType, rules: list[ImportRule]) -> ImportRule | None:
    filtered_rules = [r for r in rules if r.transaction_type == transaction_type]
    if not filtered_rules:
        return None
    
    patterns = [rule.pattern for rule in filtered_rules]
    query = pattern.lower()

    result = process.extractOne(query, patterns, score_cutoff=80)
    if result is None:
        result = process.extractOne(query, patterns, scorer=fuzz.partial_ratio, score_cutoff=85)
    if result is None:
        return None
    
    _, _, index = result
    best_rule = filtered_rules[index]
        
    return best_rule


def resolve_rule_for_classification(
        db: Session,
        description: str,
        transaction_type: TransactionType,
        entity_id: uuid.UUID|None=None,
        contact_id: uuid.UUID|None=None,
        category_id: uuid.UUID|None=None,
        is_transfer: bool=False,
        force: bool=False) -> ImportRule:
    
    all_rules = import_rule_crud.get_all(db)
    matched_rule = find_best_rule(description, transaction_type, all_rules)

    rule = None

    if matched_rule is None:
        # Caso 1: sin match — crear regla nueva
        rule = import_rule_crud.create(db, ImportRuleCreate(
            pattern=description.lower(),
            entity_id=entity_id, contact_id=contact_id, category_id=category_id,
            transaction_type=transaction_type, is_transfer=is_transfer,
        ))
    else:
        ecc_match = (
            matched_rule.entity_id == entity_id and
            matched_rule.contact_id == contact_id and
            matched_rule.category_id == category_id and
            matched_rule.transaction_type == transaction_type and
            matched_rule.is_transfer == is_transfer
        )

        if ecc_match:
            # Caso 2: ECC coincide
            rule = matched_rule
        else:
            if not force:
                # Caso 3: ECC difiere — pedir confirmación
                raise RuleConflictError(pattern=matched_rule.pattern, count=len(matched_rule.transactions))
            else:
                # Caso 3 confirmado — actualizar regla
                rule = import_rule_crud.update(db, ImportRuleUpdate(
                    entity_id=entity_id, contact_id=contact_id, category_id=category_id,
                    transaction_type=transaction_type, is_transfer=is_transfer,
                ), matched_rule)
    return rule
