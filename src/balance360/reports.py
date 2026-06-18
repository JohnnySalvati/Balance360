from datetime import date
from decimal import Decimal
from dataclasses import dataclass, field
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session
from sqlalchemy import select, func, extract, desc, true
from balance360.models.category import Category
from balance360.models.account import Account
from balance360.models.transaction import Transaction
from balance360.enums import TransactionType
from balance360.services.exchange_rate import ars_rate_subquery

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

    return category_parent_nodes



def get_account_balances(db: Session, entity_ids: list|None=None):
    
    entity_filter = Transaction.entity_id.in_(entity_ids) if entity_ids is not None else true()

    stmt = (
        select(
            Account, 
            func.coalesce(
                func.sum(Transaction.amount)
                .filter(
                    Transaction.type == TransactionType.income,
                    Transaction.is_transfer == False,
                    entity_filter
                ), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(Transaction.amount)
                .filter(
                    Transaction.type == TransactionType.expense,
                    Transaction.is_transfer == False,
                    entity_filter
                ), 0
            ).label("total_expense"),
            func.coalesce(
                ars_rate_subquery(Account.currency_id, func.current_date()), 1
            ).label("exchange_rate")
        )
        .outerjoin(Transaction, Transaction.account_id == Account.id)
        .group_by(Account.id).order_by(Account.name)
    )
    rows = db.execute(stmt).all()

    rows_data = []
    for row in rows:
        rows_data.append({
            "account": row.Account,
            "balance": row.total_income - row.total_expense,
            "ars_balance": (row.total_income - row.total_expense) * row.exchange_rate,
            "exchange_rate": row.exchange_rate,
        })

    return rows_data


def get_monthly_income_expense(db: Session, months:int =12, entity_ids: list|None=None):

    def year_from_idx(idx: int) -> int:
        return idx // 12

    def month_from_idx(idx: int) -> int:
        return idx % 12 + 1

    def get_row(idx: int):
        try:
            return next(r for r in rows if r.year == year_from_idx(idx) and r.month == month_from_idx(idx))
        except StopIteration:
            return None

    entity_filter = Transaction.entity_id.in_(entity_ids) if entity_ids is not None else true()

    current_year = date.today().year
    current_month = date.today().month
    current_idx =  current_year * 12 +  current_month - 1
    start_idx = current_idx - months + 1
    start_window = date(year_from_idx(start_idx), month_from_idx(start_idx), day=1)

    stmt = (
        select(
            extract("year", Transaction.date).label("year"),
            extract("month", Transaction.date).label("month"),
            func.coalesce(
                func.sum(Transaction.amount * 
                        func.coalesce(ars_rate_subquery(Account.currency_id, Transaction.date), 1))
                .filter(
                    Transaction.type == TransactionType.expense,
                    Transaction.is_transfer == False,
                    Transaction.date >= start_window,
                    entity_filter
                ), 0
            ).label("total_expense"),
            func.coalesce(
                func.sum(Transaction.amount *
                        func.coalesce(ars_rate_subquery(Account.currency_id, Transaction.date), 1))
                .filter(
                    Transaction.type == TransactionType.income,
                    Transaction.is_transfer == False,
                    Transaction.date >= start_window,
                    entity_filter
                ), 0
            ).label("total_income"),
        )
        .join(Account)
        .group_by("year", "month")
        .order_by("year", "month")
    )

    rows = db.execute(stmt).all()
    
    month_names = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}   
    rows_data = []

    for idx in range(start_idx, current_idx + 1):
        label = f"{month_names[month_from_idx(idx)]} {year_from_idx(idx)}"
        row = get_row(idx)
        
        rows_data.append({
            "label": label,
            "income": row.total_income if row else 0,
            "expense": row.total_expense if row else 0
        })

    return rows_data


def get_expenses_by_category(
        db: Session,
        year: int|None=None,
        month: int|None=None,
        limit:int = 6,
        entity_ids: list|None=None
):
    if year is None: year=date.today().year
    if month is None: month=date.today().month
    
    entity_filter = Transaction.entity_id.in_(entity_ids) if entity_ids is not None else true()

    stmt = (
        select(
            Category,
            func.coalesce(
                func.sum(
                    Transaction.amount * func.coalesce(ars_rate_subquery(Account.currency_id, Transaction.date), 1)
                ).filter(
                    Transaction.type == TransactionType.expense,
                    Transaction.is_transfer == False,
                    extract("year", Transaction.date) == year,
                    extract("month", Transaction.date) == month,
                    entity_filter
                    ), 0
            ).label("total_expense"),
        )
        .outerjoin(Transaction)
        .outerjoin(Account, Account.id == Transaction.account_id)
        .group_by(Category.id)
        .order_by(desc("total_expense"))
    )

    rows = db.execute(stmt).all()

    rows_data = []
    otros = 0
    for index,row in enumerate(rows):
        if index < limit:
            rows_data.append({
                "name": row.Category.name,
                "amount": row.total_expense
            })
        else:
            otros += row.total_expense
    
    if otros > 0:
        rows_data.append({
            "name": "Otros",
            "amount": otros
        })
    
    return rows_data

    