import dataclasses
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from balance360.crud import import_rule as import_rule_crud
from balance360.enums import TransactionType
from balance360.exceptions import RuleConflictError
from balance360.models.import_rule import ImportRule
from balance360.schemas.import_rule import ImportRuleCreate, ImportRuleUpdate
from balance360.services.text import normalize_pattern


@dataclass(frozen=True)
class Classification:
    entity_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    is_transfer: bool | None = False


def classification_of(rule: ImportRule) -> Classification:
    return Classification(
        entity_id=rule.entity_id,
        contact_id=rule.contact_id,
        category_id=rule.category_id,
        account_id=rule.account_id,
        is_transfer=rule.is_transfer,
    )


def extract_amount(description: str) -> Decimal | None:
    """Extract a monetary amount from a description string containing $ amounts."""
    match = re.search(r"\$\s*([\d.,]+)", description)
    if not match:
        return None
    raw = match.group(1)

    try:
        # Argentine format: dot thousands + comma decimal (e.g. 8.952,93)
        if re.match(r"^[\d.]+,\d{2}$", raw):
            normalized = raw.replace(".", "").replace(",", ".")

        # US format: has comma(s) (e.g. 68,461.96 or 1,156,611.23)
        elif "," in raw:
            normalized = raw.replace(",", "")

        # Multiple dots — typo mixing separators (e.g. 25.883.75 → 25883.75)
        elif raw.count(".") > 1:
            parts = raw.rsplit(".", 1)
            normalized = parts[0].replace(".", "") + "." + parts[1]

        # Single dot: distinguish thousands (15.800) from decimal (9196.59)
        elif "." in raw:
            _, decimal_part = raw.split(".")
            normalized = raw.replace(".", "") if len(decimal_part) == 3 else raw

        else:
            normalized = raw

        return Decimal(normalized)

    except InvalidOperation:
        return None


def find_best_rule(
    pattern: str, transaction_type: TransactionType, rules: list[ImportRule]
) -> ImportRule | None:

    filtered_rules = [r for r in rules if r.transaction_type == transaction_type]

    if not filtered_rules:
        return None

    patterns = [rule.pattern for rule in filtered_rules]
    query = normalize_pattern(pattern)

    result = process.extractOne(query, patterns, scorer=fuzz.token_set_ratio, score_cutoff=85)
    if result is None:
        return None

    _, _, index = result
    best_rule = filtered_rules[index]

    return best_rule


def resolve_rule_for_classification(
    db: Session,
    description: str,
    transaction_type: TransactionType,
    classification: Classification,
    force: bool = False,
) -> ImportRule | None:

    all_rules = import_rule_crud.get_all(db)
    matched_rule = find_best_rule(description, transaction_type, all_rules)

    rule = None

    if matched_rule is None:
        # Case 1: without match — create new rule
        pattern = normalize_pattern(description)
        if pattern:
            rule = import_rule_crud.create(
                db,
                ImportRuleCreate(
                    pattern=pattern,
                    **dataclasses.asdict(classification),
                    transaction_type=transaction_type,
                ),
            )
    else:
        if classification_of(matched_rule) == classification:
            # Case 2: match and same classification
            rule = matched_rule
        else:
            if not force:
                # Case 3 match and different classification
                raise RuleConflictError(
                    pattern=matched_rule.pattern, count=len(matched_rule.transactions)
                )
            else:
                # Case 3 match and different classification
                rule = import_rule_crud.update(
                    db,
                    ImportRuleUpdate(
                        **dataclasses.asdict(classification), transaction_type=transaction_type
                    ),
                    matched_rule,
                )
    return rule
