from dataclasses import dataclass
from typing import Optional

from apps.finance.models.transaction import Transaction
from apps.finance.models.classification_rule import ClassificationRule
from apps.finance.models.entity import EconomicEntity
from apps.finance.models.category import Category   

@dataclass
class ClassificationDelta:
    entity: Optional[EconomicEntity]
    category: Optional[Category]

def evaluate_rule(tx: Transaction, rule: ClassificationRule) -> ClassificationDelta | None:
    """
    Evalúa si una regla aplicaría a una transacción.
    NO guarda, NO muta, NO tiene efectos colaterales.
    """

    # 1. Proteger clasificaciones manuales
    if tx.classification_source == "manual":
        return None

    # 2. El patrón debe matchear
    if rule.pattern.lower() not in (tx.description or "").lower():
        return None

    new_entity = tx.entity
    new_category = tx.category
    changed = False

    # 3. Evaluar entity
    if rule.entity and (tx.entity is None or tx.classification_source == "rule"):
        if tx.entity != rule.entity:
            new_entity = rule.entity
            changed = True

    # 4. Evaluar category
    if rule.category and (tx.category is None or tx.classification_source == "rule"):
        if tx.category != rule.category:
            new_category = rule.category
            changed = True

    if not changed:
        return None

    return ClassificationDelta(
        entity=new_entity,
        category=new_category,
    )
