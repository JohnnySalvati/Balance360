from core.apps.finance.services.classification.registry import RuleRegistry

def classify_transaction(tx, *, rules=None) -> bool:
    """
    Aplica reglas a una transacción.
    Devuelve True si hubo cambios.
    """

    if tx.classification_source == "manual":
        return False

    text = tx.description.lower().strip()

    if rules is None:
        rules = RuleRegistry.get_active_rules()

    for rule in rules:
        if rule.pattern in text:
            changed = False

            if rule.entity and tx.entity != rule.entity:
                tx.entity = rule.entity
                changed = True

            if rule.category and tx.category != rule.category:
                tx.category = rule.category
                changed = True

            if changed:
                tx.classification_source = "rule"
                tx.applied_rule = rule
                tx.save(
                    update_fields=[
                        "entity",
                        "category",
                        "classification_source",
                        "applied_rule",
                    ]
                )

            return changed

    return False
