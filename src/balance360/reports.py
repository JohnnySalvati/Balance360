from collections import defaultdict

def group_by_parent(rows) -> list[dict]:
    roots = [row for row in rows if not row.Category.parent_id]
    children = [row for row in rows if row.Category.parent_id]
    children_dict = defaultdict(list)

    for child in children:
        children_dict[child.Category.parent_id].append(child)

    groups = []
    for root in roots:
        root_children = children_dict.get(root.Category.id, [])
        subtotal_income = sum(child.total_income for child in root_children) + root.total_income
        subtotal_expense = sum(child.total_expense for child in root_children) + root.total_expense
        groups.append(
            {
                'parent': root.Category,
                'parent_data': {
                    'total_income': root.total_income,
                    'total_expense': root.total_expense,
                    'net': root.total_income - root.total_expense
                } if root.total_income or root.total_expense else None,
                'children': root_children,
                'subtotal_income': subtotal_income,
                'subtotal_expense': subtotal_expense,
                'subtotal_net': subtotal_income - subtotal_expense
            }
        )
    root_ids = {root.Category.id for root in roots}
    for parent_id, parent_children in children_dict.items():
        if parent_id not in root_ids:
            subtotal_income = sum(child.total_income for child in parent_children)
            subtotal_expense = sum(child.total_expense for child in parent_children)
            groups.append(
                {
                'parent': parent_children[0].Category.parent,
                'parent_data': None,
                'children': parent_children,
                'subtotal_income': subtotal_income,
                'subtotal_expense': subtotal_expense,
                'subtotal_net': subtotal_income - subtotal_expense
                }
            )
    return sorted(groups, key=lambda group: group["parent"].name)