from apps.finance.models import EconomicEntity


def get_consolidated_entities(entity: EconomicEntity):

    children = EconomicEntity.objects.filter(
        parent_links__parent=entity
    )

    if children.exists():
        # Incluimos también la entidad padre (por si tiene movimientos propios)
        return list(children) + [entity]

    return [entity]
