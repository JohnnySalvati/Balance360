from collections import defaultdict
from decimal import Decimal
from dataclasses import dataclass, field
from sqlalchemy.engine import Row
from balance360.models.category import Category

@dataclass
class CategoryNode:
    category: Category
    income: Decimal
    expense: Decimal
    subtotal_income: Decimal
    subtotal_expense: Decimal
    children: list['CategoryNode'] = field(default_factory=list)

def get_children(node: CategoryNode, nodes: list[CategoryNode]) -> list[CategoryNode]:
    node_children = [n for n in nodes if n.category.parent_id == node.category.id]
    for node_child in node_children:
        node_child.children = get_children(node_child, nodes)
        node.subtotal_income += node_child.subtotal_income
        node.subtotal_expense += node_child.subtotal_expense
    node.subtotal_income += node.income
    node.subtotal_expense += node.expense
    return node_children

def build_category_tree(rows: list[Row]) -> list[CategoryNode]:
    """
    rows: resultado de db.execute() con columnas (Category, total_income, total_expense)
    """
    category_parent_nodes = [CategoryNode(
        category=row.Category,
        income=row.total_income,
        expense=row.total_expense,
        subtotal_income=Decimal(0),
        subtotal_expense=Decimal(0),
        children=[]
    )for row in rows if row.Category.parent_id == None]

    category_nodes = [CategoryNode(
        category=row.Category,
        income=row.total_income,
        expense=row.total_expense,
        subtotal_income=Decimal(0),
        subtotal_expense=Decimal(0),
        children=[]
    )for row in rows if row.Category.parent_id != None]
   
    for category_parent_node in category_parent_nodes:
        category_parent_node.children = get_children(category_parent_node, category_nodes)

    print(category_parent_nodes)
    return category_parent_nodes
