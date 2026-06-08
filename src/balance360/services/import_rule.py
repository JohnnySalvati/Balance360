import re
from decimal import Decimal, InvalidOperation
from rapidfuzz import process, fuzz
from balance360.models.import_rule import ImportRule
from balance360.enums import TransactionType


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

def find_best_rule(pattern: str, transaction_type: TransactionType, rules: list[ImportRule], amount: Decimal) -> ImportRule | None:
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

    matching_rules = [r for r in filtered_rules if r.pattern == best_rule.pattern]

    for rule in matching_rules:
        if rule.min_amount <= amount <= rule.max_amount:
            return rule
        
    return None

