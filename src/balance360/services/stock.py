import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, case, func, not_, or_, select
from sqlalchemy.orm import Session

from balance360.enums import InvoiceType, VoucherType
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.models.product import Product


@dataclass
class Stock:
    id: uuid.UUID
    name: str
    stock_qty: int
    unit_price: Decimal
    valuation: Decimal


is_nc = func.coalesce(
    Invoice.voucher_type.in_((VoucherType.NCA, VoucherType.NCB, VoucherType.NCC)), False
)

is_positive = or_(
    and_(Invoice.invoice_type == InvoiceType.purchase, not_(is_nc)),
    and_(Invoice.invoice_type == InvoiceType.sale, is_nc),
)


def get_stock_summary(db: Session, entity_id: uuid.UUID | None = None) -> list[Stock]:

    last_price_sq = (
        select(InvoiceLine.unit_price)
        .join(Invoice)
        .where(Invoice.confirmed)
        .where(Invoice.invoice_type == InvoiceType.purchase)
        .where(InvoiceLine.product_id == Product.id)
        .order_by(Invoice.date.desc())
        .limit(1)
        .correlate(Product)
    )
    if entity_id:
        last_price_sq = last_price_sq.where(Invoice.entity_id == entity_id)

    last_price_sq = last_price_sq.scalar_subquery()

    stmt = (
        select(
            Product.name,
            func.sum(
                case(
                    (is_positive, InvoiceLine.quantity),
                    else_=-InvoiceLine.quantity,
                )
            ).label("stock_qty"),
            last_price_sq.label("unit_price"),
            Product.id.label("id"),
        )
        .join(InvoiceLine, InvoiceLine.product_id == Product.id)
        .join(Invoice)
        .where(Invoice.confirmed)
        .group_by(Product.id)
    )

    if entity_id:
        stmt = stmt.where(Invoice.entity_id == entity_id)

    rows = db.execute(stmt).all()
    return [
        Stock(
            id=row.id,
            name=row.name,
            stock_qty=row.stock_qty,
            unit_price=row.unit_price,
            valuation=row.stock_qty * row.unit_price if row.unit_price else Decimal(0),
        )
        for row in rows
    ]


def get_product_stock(db, product_id, entity_id) -> int:

    stmt = (
        select(
            func.sum(
                case(
                    (is_positive, InvoiceLine.quantity),
                    else_=-InvoiceLine.quantity,
                )
            ).label("stock_qty"),
        )
        .join(Invoice)
        .where(Invoice.confirmed)
        .where(InvoiceLine.product_id == product_id)
        .where(Invoice.entity_id == entity_id)
    )
    quantity = db.execute(stmt).scalar()

    return quantity or 0
