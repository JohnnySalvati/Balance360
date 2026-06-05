import uuid
from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session
from balance360.models.invoice_line import InvoiceLine
from balance360.models.invoice import Invoice
from balance360.models.product import Product
from balance360.enums import InvoiceType

@dataclass
class Stock:
    id: uuid.UUID
    name: str
    stock_qty: int
    unit_price: Decimal
    valuation: Decimal

def get_stock_summary(db: Session) -> list[Stock]:

    last_price_sq = (
        select(InvoiceLine.unit_price)
        .join(Invoice)
        .where(Invoice.confirmed)
        .where(Invoice.invoice_type == InvoiceType.purchase)
        .where(InvoiceLine.product_id == Product.id)
        .order_by(Invoice.date.desc())
        .limit(1)
        .correlate(Product)
        .scalar_subquery()
    )

    stmt = (
        select(Product.name,
               func.sum(
                   case(
                       (Invoice.invoice_type == InvoiceType.purchase, InvoiceLine.quantity),
                       else_=-InvoiceLine.quantity
                   )
               ).label("stock_qty"),
               last_price_sq.label("unit_price"),
               Product.id.label("id")
        )
        .join(InvoiceLine, InvoiceLine.product_id == Product.id)
        .join(Invoice)
        .where(Invoice.confirmed)
        .group_by(Product.id)
    )

    rows = db.execute(stmt).all()
    return [
        Stock(
            id=row.id,
            name=row.name,
            stock_qty=row.stock_qty,
            unit_price=row.unit_price,
            valuation= row.stock_qty * row.unit_price if row.unit_price else Decimal(0)
        ) for row in rows
    ]
