from rapidfuzz import process, fuzz
from balance360.models.import_rule import ImportRule
from balance360.enums import TransactionType

def find_best_rule(description: str, transaction_type: TransactionType, rules: list[ImportRule]) -> ImportRule | None:
    filtered_rules = [r for r in rules if r.transaction_type == transaction_type]
    if not filtered_rules:
        return None
    
    patterns = [rule.pattern for rule in filtered_rules]
    query = description.lower()

    result = process.extractOne(query, patterns, score_cutoff=80)
    if result is None:
        result = process.extractOne(query, patterns, scorer=fuzz.partial_ratio, score_cutoff=85)
    if result is None:
        return None
    
    _, _, index = result
    return filtered_rules[index]


