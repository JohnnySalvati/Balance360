import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, case, func, not_, or_, select
from sqlalchemy.orm import Session, aliased

from balance360.enums import InvoiceType, VoucherType
from balance360.models.invoice import Invoice
from balance360.models.invoice_line import InvoiceLine
from balance360.models.money import money
from balance360.models.product import Product


@dataclass
class Stock:
    id: uuid.UUID
    name: str
    stock_qty: int
    pending_in: int
    pending_out: int
    # El ultimo costo de reposicion, con el IVA adentro. `None` = nunca se compro.
    gross_unit_price: Decimal | None

    @property
    def available_qty(self) -> int:
        """Lo que queda por vender: lo que hay menos lo que ya esta vendido sin entregar."""
        return self.stock_qty - self.pending_out

    @property
    def valuation(self) -> Decimal:
        """Lo que vale lo que todavia se puede vender.

        Sobre `available_qty` y no sobre el fisico: la unidad vendida y no entregada
        esta en el estante pero ya tiene dueño, asi que sumarla al valor del deposito
        cuenta dos veces la misma plata —una acá y otra en lo que falta cobrar—.

        Es una propiedad y no un campo para que no pueda quedar desincronizada de las
        dos cosas de las que depende, que es lo que pasaba cuando se calculaba en el
        constructor.

        Con mas comprometido que fisico da negativo, y se deja asi: significa que hay
        prometido lo que no existe, y esconderlo con un max(0) borraria justo el numero
        que hay que mirar.
        """
        if self.gross_unit_price is None:
            return Decimal(0)
        return self.available_qty * self.gross_unit_price


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

# Un producto con las cuatro columnas en cero no tiene nada que mirar: ni en el estante,
# ni prometido, ni en camino. Lo tipico es el producto agotado —se compraron cinco y se
# vendieron las cinco—, que se queda en la pantalla para siempre porque tuvo movimientos
# alguna vez, y con el catalogo entero adentro la pantalla deja de mostrar lo que hay.
#
# Van tres condiciones y no cuatro porque `disponible` es `fisico - comprometido`: si los
# dos son cero, disponible tambien, y si disponible no es cero entonces esos dos son
# distintos entre si y no pueden ser los dos cero. La cuarta columna ya esta cubierta.
#
# Es HAVING y no un filtro en Python: descartar despues significa traer todas las filas
# igual, y este es el `select` que crece con cada producto que entra al catalogo.
_has_quantity = or_(_stock_qty != 0, _pending_in != 0, _pending_out != 0)

# El IVA se suma solo cuando la letra lo aplica, que es la misma regla que
# `Invoice.applies_iva`. Hace falta porque nada impide que una compra C guarde una
# alicuota en la linea: `iva_breakdown` la ignora al mostrar, pero la columna queda
# escrita igual, y multiplicar a ciegas inflaria un 21% un costo que ya era final.
#
# El `coalesce` es el gotcha de siempre: `notin_` sobre un `voucher_type` NULL —todo
# comprobante informal— devuelve NULL y no True, y el `case` caeria al `else_`. Da lo
# mismo en el numero, porque un informal no puede llevar IVA, pero la condicion estaria
# diciendo lo contrario de lo que se quiere.
_applies_iva = func.coalesce(Invoice.voucher_type.notin_((VoucherType.C, VoucherType.NCC)), True)

# El unitario se guarda siempre neto (ver el comentario de `InvoiceLine.unit_price`),
# asi que el bruto se deriva acá y no sale de ninguna columna.
_gross_unit_price = case(
    (_applies_iva, InvoiceLine.unit_price * (1 + InvoiceLine.iva_rate / 100)),
    else_=InvoiceLine.unit_price,
)


def get_stock_summary(db: Session, entity_id: uuid.UUID | None = None) -> list[Stock]:

    last_price_sq = (
        select(_gross_unit_price)
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
            last_price_sq.label("gross_unit_price"),
            Product.id.label("id"),
        )
        .join(InvoiceLine, InvoiceLine.product_id == Product.id)
        .join(Invoice)
        .where(Invoice.confirmed)
        .group_by(Product.id)
        .having(_has_quantity)
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
            # El redondeo se hace acá, sobre el unitario, y no en SQL: `money()` es el
            # ROUND_HALF_UP unificado de la app, y redondear el unitario antes de
            # multiplicarlo por la cantidad es lo mismo que hace `InvoiceLine.gross_amount`.
            gross_unit_price=money(row.gross_unit_price)
            if row.gross_unit_price is not None
            else None,
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
