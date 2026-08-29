import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.invoice import Invoice
    from balance360.models.product import Product
    from balance360.models.serial_number import SerialNumber
from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from balance360.enums import IvaAliquot
from balance360.models.base import Base, TimestampMixin
from balance360.models.money import money


class InvoiceLine(Base, TimestampMixin):
    __tablename__ = "invoice_lines"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="CASCADE")
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("products.id"))
    description: Mapped[str | None] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Cuatro decimales y no dos, y el motivo es entero de la integración con FactuMov.
    #
    # Acá el precio unitario se guarda **neto** siempre: para una factura B, el bruto se
    # deriva (`gross_unit_price = money(unit_price * (1 + iva_rate/100))`). FactuMov hace lo
    # contrario —en B guarda el precio con el IVA adentro, que es como se carga y como se
    # imprime—, así que registrar una B suya obliga a convertir el precio a neto acá.
    #
    # Con dos decimales esa conversión **no cierra**, y no es un caso raro: una B de $100 al
    # 21% necesita un neto de 82,6446. El más cercano de dos decimales es 82,64, que vuelve a
    # dar 99,99 — un centavo menos que lo que ARCA autorizó. Con 82,65 da 100,01. O sea que el
    # total de $100 era **inexpresable**, y un comprobante autorizado cuyo total no es el del
    # CAE es exactamente lo que `IssuedInvoiceMismatchError` no deja entrar.
    #
    # El cambio es una ampliación: los precios que ya estaban tienen dos decimales y siguen
    # valiendo lo mismo. Lo único que se ve distinto es una línea traída de FactuMov, que
    # puede mostrar un unitario con cuatro decimales — el importe de la línea, que es lo que
    # se lee, sigue redondeado a dos por `money()`.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=4))
    iva_aliquot: Mapped[IvaAliquot] = mapped_column(
        Enum(IvaAliquot, values_callable=lambda obj: [e.name for e in obj])
    )
    iva_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    invoice: Mapped["Invoice"] = relationship(
        foreign_keys="InvoiceLine.invoice_id", back_populates="invoice_lines"
    )
    product: Mapped["Product"] = relationship(back_populates="invoice_lines")
    purchased_serials: Mapped[list["SerialNumber"]] = relationship(
        foreign_keys="SerialNumber.purchase_line_id",
        back_populates="purchase_line",
        cascade="all, delete-orphan",
    )
    sold_serials: Mapped[list["SerialNumber"]] = relationship(
        foreign_keys="SerialNumber.sale_line_id", back_populates="sale_line", passive_deletes=True
    )

    @property
    def net_amount(self) -> Decimal:
        return self.quantity * self.unit_price

    @property
    def gross_unit_price(self) -> Decimal:
        return money(self.unit_price * (1 + self.iva_rate / 100))

    @property
    def gross_amount(self) -> Decimal:
        return self.gross_unit_price * self.quantity

    @validates("iva_aliquot")
    def validates_iva_aliquot(self, key, value) -> IvaAliquot:
        self.iva_rate = value.rate
        return value
