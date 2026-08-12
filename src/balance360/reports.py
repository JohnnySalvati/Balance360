from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import case, desc, extract, func, not_, or_, select, true
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from balance360.enums import InvoiceType, TransactionType, VoucherType
from balance360.models.account import Account
from balance360.models.category import Category
from balance360.models.currency import Currency
from balance360.models.entity import Entity
from balance360.models.fiscal_identity import FiscalIdentity
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.models.invoice_tribute import InvoiceTribute
from balance360.models.transaction import Transaction
from balance360.services.exchange_rate import conversion_factor

nc_case = case(
    (Invoice.voucher_type.in_([VoucherType.NCA, VoucherType.NCB, VoucherType.NCC]), -1), else_=1
)
@dataclass
class CategoryNode:
    category: Category
    income: Decimal
    expense: Decimal
    subtotal_income: Decimal
    subtotal_expense: Decimal
    children: list["CategoryNode"] = field(default_factory=list)


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
    category_parent_nodes = [
        CategoryNode(
            category=row.Category,
            income=row.total_income,
            expense=row.total_expense,
            subtotal_income=Decimal(0),
            subtotal_expense=Decimal(0),
            children=[],
        )
        for row in rows
        if row.Category.parent_id is None
    ]

    category_nodes = [
        CategoryNode(
            category=row.Category,
            income=row.total_income,
            expense=row.total_expense,
            subtotal_income=Decimal(0),
            subtotal_expense=Decimal(0),
            children=[],
        )
        for row in rows
        if row.Category.parent_id is not None
    ]

    for category_parent_node in category_parent_nodes:
        category_parent_node.children = get_children(category_parent_node, category_nodes)

    return category_parent_nodes


def get_account_balances(
    db: Session,
    entity_ids: list | None = None,
    to_currency: Currency | None = None,
    reference_date: date | None = None,
):

    if not reference_date:
        reference_date = date.today()

    entity_filter = Transaction.entity_id.in_(entity_ids) if entity_ids is not None else true()

    stmt = (
        select(
            Account,
            func.coalesce(
                func.sum(Transaction.amount).filter(
                    Transaction.type == TransactionType.income,
                    Transaction.is_transfer.is_(False),
                    entity_filter,
                ),
                0,
            ).label("total_income"),
            func.coalesce(
                func.sum(Transaction.amount).filter(
                    Transaction.type == TransactionType.expense,
                    Transaction.is_transfer.is_(False),
                    entity_filter,
                ),
                0,
            ).label("total_expense"),
            func.coalesce(
                conversion_factor(
                    source_id=Account.currency_id,
                    txn_date=func.current_date(),
                    target_currency=to_currency,
                    reference_date=reference_date,
                ),
                1,
            ).label("exchange_rate"),
        )
        .outerjoin(Transaction, Transaction.account_id == Account.id)
        .group_by(Account.id)
        .order_by(Account.name)
    )
    rows = db.execute(stmt).all()

    rows_data = []
    for row in rows:
        rows_data.append(
            {
                "account": row.Account,
                "balance": row.total_income - row.total_expense,
                "ars_balance": (row.total_income - row.total_expense) * row.exchange_rate,
                "exchange_rate": row.exchange_rate,
            }
        )

    return rows_data


def get_monthly_income_expense(
    db: Session,
    months: int = 12,
    entity_ids: list | None = None,
    to_currency: Currency | None = None,
    reference_date: date | None = None,
):

    def year_from_idx(idx: int) -> int:
        return idx // 12

    def month_from_idx(idx: int) -> int:
        return idx % 12 + 1

    def get_row(idx: int):
        try:
            return next(
                r for r in rows if r.year == year_from_idx(idx) and r.month == month_from_idx(idx)
            )
        except StopIteration:
            return None

    if not reference_date:
        reference_date = date.today()

    entity_filter = Transaction.entity_id.in_(entity_ids) if entity_ids is not None else true()

    current_year = date.today().year
    current_month = date.today().month
    current_idx = current_year * 12 + current_month - 1
    start_idx = current_idx - months + 1
    start_window = date(year_from_idx(start_idx), month_from_idx(start_idx), day=1)

    stmt = (
        select(
            extract("year", Transaction.date).label("year"),
            extract("month", Transaction.date).label("month"),
            func.coalesce(
                func.sum(
                    Transaction.amount
                    * conversion_factor(
                        source_id=Account.currency_id,
                        txn_date=Transaction.date,
                        target_currency=to_currency,
                        reference_date=reference_date,
                    )
                ).filter(
                    Transaction.type == TransactionType.expense,
                    Transaction.is_transfer.is_(False),
                    Transaction.date >= start_window,
                    entity_filter,
                ),
                0,
            ).label("total_expense"),
            func.coalesce(
                func.sum(
                    Transaction.amount
                    * conversion_factor(
                        source_id=Account.currency_id,
                        txn_date=Transaction.date,
                        target_currency=to_currency,
                        reference_date=reference_date,
                    )
                ).filter(
                    Transaction.type == TransactionType.income,
                    Transaction.is_transfer.is_(False),
                    Transaction.date >= start_window,
                    entity_filter,
                ),
                0,
            ).label("total_income"),
        )
        .join(Account)
        .group_by("year", "month")
        .order_by("year", "month")
    )

    rows = db.execute(stmt).all()

    month_names = {
        1: "Ene",
        2: "Feb",
        3: "Mar",
        4: "Abr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dic",
    }
    rows_data = []

    for idx in range(start_idx, current_idx + 1):
        label = f"{month_names[month_from_idx(idx)]} {year_from_idx(idx)}"
        row = get_row(idx)

        rows_data.append(
            {
                "label": label,
                "income": row.total_income if row else 0,
                "expense": row.total_expense if row else 0,
            }
        )

    return rows_data

# def get_monthly_profit(
#     db: Session,
#     months: int = 12,
#     entity_ids: list | None = None,
#     to_currency: Currency | None = None,
#     reference_date: date | None = None
# :)

def get_expenses_by_category(
    db: Session,
    year: int | None = None,
    month: int | None = None,
    limit: int = 6,
    entity_ids: list | None = None,
    to_currency: Currency | None = None,
    reference_date: date | None = None,
):
    if year is None:
        year = date.today().year
    if month is None:
        month = date.today().month

    if not reference_date:
        reference_date = date.today()

    entity_filter = Transaction.entity_id.in_(entity_ids) if entity_ids is not None else true()

    stmt = (
        select(
            Category,
            func.coalesce(
                func.sum(
                    Transaction.amount
                    * conversion_factor(
                        source_id=Account.currency_id,
                        txn_date=Transaction.date,
                        target_currency=to_currency,
                        reference_date=reference_date,
                    )
                ).filter(
                    Transaction.type == TransactionType.expense,
                    Transaction.is_transfer.is_(False),
                    extract("year", Transaction.date) == year,
                    extract("month", Transaction.date) == month,
                    entity_filter,
                ),
                0,
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
    for index, row in enumerate(rows):
        if index < limit:
            rows_data.append({"name": row.Category.name, "amount": row.total_expense})
        else:
            otros += row.total_expense

    if otros > 0:
        rows_data.append({"name": "Otros", "amount": otros})

    return rows_data


def get_iva_position(
    db: Session,
    start: date,
    end: date,
    entity_ids: list | None = None,
    to_currency: Currency | None = None,
    reference_date: date | None = None,
) -> dict:

    if not reference_date:
        reference_date = date.today()

    entity_filter = Invoice.entity_id.in_(entity_ids) if entity_ids is not None else true()

    stmt = (
        select(
            Entity.id.label("entity_id"),
            Entity.name.label("entity_name"),
            func.coalesce(
                func.sum(
                    InvoiceLine.quantity
                    * InvoiceLine.unit_price
                    * InvoiceLine.iva_rate
                    / 100
                    * nc_case
                    * conversion_factor(
                        source_id=None,
                        txn_date=Invoice.date,
                        target_currency=to_currency,
                        reference_date=reference_date,
                    )
                ).filter(
                    Invoice.invoice_type == InvoiceType.sale,
                    Invoice.applies_iva
                ),
                0,
            ).label("debit"),
            func.coalesce(
                func.sum(
                    InvoiceLine.quantity
                    * InvoiceLine.unit_price
                    * InvoiceLine.iva_rate
                    / 100
                    * nc_case
                    * conversion_factor(
                        source_id=None,
                        txn_date=Invoice.date,
                        target_currency=to_currency,
                        reference_date=reference_date,
                    )
                ).filter(
                    Invoice.invoice_type == InvoiceType.purchase,
                    Invoice.applies_iva
                ),
                0,
            ).label("credit"),
        )
        .where(Invoice.date.between(start, end))
        .where(Invoice.confirmed)
        .where(or_(Invoice.formal, Invoice.tax_only))
        .where(entity_filter)
        .join_from(Entity, Invoice)
        .join_from(Invoice, InvoiceLine)
        .group_by(Entity.id)
        .order_by(Entity.name)
    )
    rows = db.execute(stmt).all()

    by_entity = [
        {
            "entity_id": row.entity_id,
            "entity_name": row.entity_name,
            "debit": row.debit,
            "credit": row.credit,
            "position": row.debit - row.credit,
        }
        for row in rows
    ]

    total_debits = sum(entity["debit"] for entity in by_entity)

    total_credits = sum(entity["credit"] for entity in by_entity)

    return {
        "by_entity": by_entity,
        "total": {
            "total_debits": total_debits,
            "total_credits": total_credits,
            "position": total_debits - total_credits,
        },
    }


def get_tributes(
    db: Session,
    start: date,
    end: date,
    entity_ids: list | None = None,
    to_currency: Currency | None = None,
    reference_date: date | None = None,
) -> dict:

    if not reference_date:
        reference_date = date.today()

    entity_filter = Invoice.entity_id.in_(entity_ids) if entity_ids is not None else true()

    stmt = (
        select(
            Entity.id.label("entity_id"),
            Entity.name.label("entity_name"),
            InvoiceTribute.tribute_type.label("tribute_type"),
            func.sum(
                InvoiceTribute.base_amount
                * InvoiceTribute.rate
                / 100
                * conversion_factor(
                    source_id=None,
                    txn_date=Invoice.date,
                    target_currency=to_currency,
                    reference_date=reference_date,
                )
            ).label("total_invoice"),
        )
        .where(Invoice.date.between(start, end))
        .where(Invoice.confirmed)
        .where(or_(Invoice.formal, Invoice.tax_only))
        .where(entity_filter)
        .join_from(Entity, Invoice)
        .join_from(Invoice, InvoiceTribute)
        .group_by(Entity.id, InvoiceTribute.tribute_type)
        .order_by(Entity.name, InvoiceTribute.tribute_type)
    )

    rows = db.execute(stmt).all()

    entity_id = rows[0].entity_id if rows else None
    entity_name = rows[0].entity_name if rows else None
    entity_total = 0
    tributes_by_entity = []
    total = 0
    by_entity = []

    for row in rows:
        if row.entity_id == entity_id:
            entity_total += row.total_invoice
            tributes_by_entity.append(
                {"tribute_type": row.tribute_type, "total_invoice": row.total_invoice}
            )
        else:
            by_entity.append(
                {
                    "entity_id": entity_id,
                    "entity_name": entity_name,
                    "tributes_by_entity": tributes_by_entity,
                    "entity_total": entity_total,
                }
            )
            total += entity_total
            entity_id = row.entity_id
            entity_name = row.entity_name
            entity_total = row.total_invoice
            tributes_by_entity = [
                {"tribute_type": row.tribute_type, "total_invoice": row.total_invoice}
            ]

    if rows:
        by_entity.append(
            {
                "entity_id": entity_id,
                "entity_name": entity_name,
                "tributes_by_entity": tributes_by_entity,
                "entity_total": entity_total,
            }
        )
        total += entity_total

    return {"by_entity": by_entity, "total": total}


def get_iibb_on_sales(
    db: Session,
    start: date,
    end: date,
    entity_ids: list | None = None,
    to_currency: Currency | None = None,
    reference_date: date | None = None,
) -> dict:

    if not reference_date:
        reference_date = date.today()

    entity_filter = Invoice.entity_id.in_(entity_ids) if entity_ids is not None else true()

    stmt = (
        select(
            Entity.id.label("entity_id"),
            Entity.name.label("entity_name"),
            func.sum(
                InvoiceLine.quantity
                * InvoiceLine.unit_price
                * FiscalIdentity.iibb_rate
                / 100
                * nc_case
                * conversion_factor(
                    source_id=None,
                    txn_date=Invoice.date,
                    target_currency=to_currency,
                    reference_date=reference_date,
                )
            ).label("entity_total"),
        )
        .where(Invoice.date.between(start, end))
        .where(Invoice.confirmed)
        .where(Invoice.formal)
        .where(entity_filter)
        .where(Invoice.invoice_type == InvoiceType.sale)
        .join_from(Entity, Invoice)
        .join_from(Invoice, InvoiceLine)
        .join_from(Invoice, FiscalIdentity, Invoice.fiscal_identity_id == FiscalIdentity.id)
        .group_by(Entity.id)
        .order_by(Entity.name)
    )

    rows = db.execute(stmt).all()

    by_entity = [
        {
            "entity_id": row.entity_id,
            "entity_name": row.entity_name,
            "entity_total": row.entity_total,
        }
        for row in rows
    ]

    total = sum(entity["entity_total"] for entity in by_entity)

    return {"by_entity": by_entity, "total": total}


def get_invoice_profit(
    db: Session,
    start: date,
    end: date,
    entity_ids: list | None = None,
    to_currency: Currency | None = None,
    reference_date: date | None = None,
) -> dict:

    if not reference_date:
        reference_date = date.today()

    entity_filter = Invoice.entity_id.in_(entity_ids) if entity_ids is not None else true()


    applies_iva_case = case(
        (Invoice.applies_iva,
        1 + InvoiceLine.iva_rate/100),
        else_=1
    )

    stmt = (
        select(
            Entity.id.label("entity_id"),
            Entity.name.label("entity_name"),
            func.coalesce(
                func.sum(
                    InvoiceLine.quantity
                    * InvoiceLine.unit_price
                    * nc_case
                    * conversion_factor(
                        source_id=None,
                        txn_date=Invoice.date,
                        target_currency=to_currency,
                        reference_date=reference_date,
                    )
                ).filter(Invoice.invoice_type == InvoiceType.sale),
                0,
            ).label("net_sales"),
            func.coalesce(
                func.sum(
                    InvoiceLine.quantity
                    * InvoiceLine.unit_price
                    * nc_case
                    * conversion_factor(
                        source_id=None,
                        txn_date=Invoice.date,
                        target_currency=to_currency,
                        reference_date=reference_date,
                    )
                ).filter(Invoice.invoice_type == InvoiceType.purchase),
                0,
            ).label("net_purchases"),
            func.coalesce(
                func.sum(
                    InvoiceLine.quantity
                    * InvoiceLine.unit_price
                    * nc_case
                    * applies_iva_case
                    * conversion_factor(
                        source_id=None,
                        txn_date=Invoice.date,
                        target_currency=to_currency,
                        reference_date=reference_date,
                    )
                ).filter(Invoice.invoice_type == InvoiceType.sale),
                0,
            ).label("gross_sales"),
            func.coalesce(
                func.sum(
                    InvoiceLine.quantity
                    * InvoiceLine.unit_price
                    * nc_case
                    * applies_iva_case
                    * conversion_factor(
                        source_id=None,
                        txn_date=Invoice.date,
                        target_currency=to_currency,
                        reference_date=reference_date,
                    )
                ).filter(Invoice.invoice_type == InvoiceType.purchase),
                0,
            ).label("gross_purchases"),
        )
        .where(Invoice.date.between(start, end))
        .where(Invoice.confirmed)
        .where(entity_filter)
        .where(not_(Invoice.tax_only))
        .join_from(Entity, Invoice)
        .join_from(Invoice, InvoiceLine)
        .group_by(Entity.id)
        .order_by(Entity.id)
    )

    rows = db.execute(stmt).all()

    entities_profit = [
        {
            "entity_id": row.entity_id,
            "entity_name": row.entity_name,
            "net_sales": row.net_sales,
            "net_purchases": row.net_purchases,
            "gross_sales": row.gross_sales,
            "gross_purchases": row.gross_purchases
        }
        for row in rows
    ]

    iibb_by_entity = get_iibb_on_sales(
        db,
        start=start,
        end=end,
        entity_ids=entity_ids,
        to_currency=to_currency,
        reference_date=reference_date,
    )

    tributes_by_entity = get_tributes(
        db,
        start=start,
        end=end,
        entity_ids=entity_ids,
        to_currency=to_currency,
        reference_date=reference_date,
    )

    iva_by_entity = get_iva_position(
        db,
        start=start,
        end=end,
        entity_ids=entity_ids,
        to_currency=to_currency,
        reference_date=reference_date,
    )

    profit_idx = {e["entity_id"]: e for e in entities_profit}
    iva_idx = {e["entity_id"]: e for e in iva_by_entity["by_entity"]}
    trib_idx = {e["entity_id"]: e for e in tributes_by_entity["by_entity"]}
    iibb_idx = {e["entity_id"]: e for e in iibb_by_entity["by_entity"]}

    ids = profit_idx.keys() | iva_idx.keys() | trib_idx.keys() | iibb_idx.keys()

    by_entity = []
    total = 0
    for eid in ids:
        p = profit_idx.get(eid, {})
        iva = iva_idx.get(eid, {})
        trib = trib_idx.get(eid, {})
        iibb = iibb_idx.get(eid, {})

        entity_name = (p or iva or trib or iibb).get("entity_name")

        margin = p.get("net_sales", 0) - p.get("net_purchases", 0) 

        gross_profit = p.get("gross_sales", 0) - p.get("gross_purchases", 0) 

        iva_position = iva.get("position", 0)

        special_iva_credit = (gross_profit - margin) - iva_position

        tributes = trib.get("entity_total", 0)

        iibb = iibb.get("entity_total", 0)
        
        taxes = iva_position + tributes + iibb

        net_profit = margin - iibb - tributes
        
        by_entity.append(
            {
                "entity_id": eid,
                "entity_name": entity_name,
                "gross_profit": gross_profit,
                "taxes": taxes,
                "special_iva_credit": special_iva_credit,
                "net_profit": net_profit,
            }
        )
        total += net_profit

    return {"by_entity": by_entity, "total": total}
