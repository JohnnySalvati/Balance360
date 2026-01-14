from apps.finance.models.classification_rule import ClassificationRule

def classify_transaction(tx):
    text = tx.description.lower()

    rules = (
        ClassificationRule.objects
        .filter(is_active=True)
        .order_by("-confidence")
    )

    for rule in rules:
        if rule.pattern in text:
            changed = False

            if tx.entity != rule.entity:
                tx.entity = rule.entity
                changed = True

            if tx.category != rule.category:
                tx.category = rule.category
                changed = True

            if changed:
                tx.save(update_fields=["entity", "category"])

            return True

    return False
