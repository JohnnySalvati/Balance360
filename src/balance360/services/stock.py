import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, case, func, not_, or_, select
from sqlalchemy.orm import Session, aliased

from balance360.enums import InvoiceType, VoucherType
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.models.product import Product


@dataclass
class Stock:
    id: uuid.UUID
    name: str
    stock_qty: int
    pending_in: int
    pending_out: int
    unit_price: Decimal
    valuation: Decimal

    @property
    def available_qty(self) -> int:
        """Lo que queda por vender: lo que hay menos lo que ya esta vendido sin entregar."""
        return self.stock_qty - self.pending_out


is_nc = func.coalesce(
    Invoice.voucher_type.in_((VoucherType.NCA, VoucherType.NCB, VoucherType.NCC)), False
)

is_positive = or_(
    and_(Invoice.invoice_type == InvoiceType.purchase, not_(is_nc)),
    and_(Invoice.invoice_type == InvoiceType.sale, is_nc),
)

# Una NC revierte el movimiento del comprobante original. Cuando el original nunca se
# movio —la venta anticipada que se cae antes de la entrega— no hay nada que revertir:
# esa NC queda cumplida sin mover una sola unidad, y contarla sumaria al deposito stock
# que jamas salio de el. Una NC sin original (cargada a mano desde el portal de ARCA) si
# se toma al pie de la letra: no hay contra que compararla.
_original = aliased(Invoice)
_reverses_nothing = (
    select(1)
    .where(_original.id == Invoice.related_invoice_id, _original.fulfilled_at.is_(None))
    .exists()
)

# El stock cuenta el movimiento fisico, no el hecho fiscal: una venta facturada para
# anticipar el cobro no descuenta nada hasta que se entrega, y la compra del proveedor
# no suma hasta que llega. Antes las dos cosas eran `confirmed` porque ocurrian juntas.
_moved = and_(Invoice.fulfilled_at.is_not(None), not_(_reverses_nothing))

# Un comprobante confirmado y sin mover es un compromiso: lo que falta entregar o lo que
# esta por llegar. Deja de serlo cuando una NC confirmada lo anula.
_annulling_nc = aliased(Invoice)
_annulled = (
    select(1)
    .where(_annulling_nc.related_invoice_id == Invoice.id, _annulling_nc.confirmed)
    .exists()
)
_committed = and_(Invoice.fulfilled_at.is_(None), not_(_annulled))

_signed_qty = case((is_positive, InvoiceLine.quantity), else_=-InvoiceLine.quantity)

# Las tres columnas salen de la misma consulta a proposito: un producto que solo tiene
# movimientos pendientes —lo tipico de una venta anticipada— tiene que aparecer igual,
# y filtrando por `_moved` en el WHERE no aparecia.
_stock_qty = func.sum(case((_moved, _signed_qty), else_=0))
_pending_in = func.sum(case((and_(_committed, is_positive), InvoiceLine.quantity), else_=0))
_pending_out = func.sum(case((and_(_committed, not_(is_positive)), InvoiceLine.quantity), else_=0))


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
            _stock_qty.label("stock_qty"),
            _pending_in.label("pending_in"),
            _pending_out.label("pending_out"),
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
            pending_in=row.pending_in,
            pending_out=row.pending_out,
            unit_price=row.unit_price,
            valuation=row.stock_qty * row.unit_price if row.unit_price else Decimal(0),
        )
        for row in rows
    ]


def get_product_stock(db, product_id, entity_id) -> int:
    """Unidades fisicas en deposito. Es lo que se puede entregar hoy.

    No descuenta lo comprometido a proposito: quien pregunta es la validacion de la
    entrega, y ahi la pregunta es si la unidad esta, no si esta prometida a alguien.
    """

    stmt = (
        select(func.sum(_signed_qty).label("stock_qty"))
        .join(Invoice)
        .where(Invoice.confirmed)
        .where(_moved)
        .where(InvoiceLine.product_id == product_id)
        .where(Invoice.entity_id == entity_id)
    )
    quantity = db.execute(stmt).scalar()

    return quantity or 0
