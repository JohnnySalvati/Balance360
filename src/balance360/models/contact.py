from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.import_rule import ImportRule
    from balance360.models.invoice import Invoice
    from balance360.models.transaction import Transaction
import uuid

from sqlalchemy import Enum, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.enums import CondicionIva, ContactType, DocType
from balance360.models.base import Base, TimestampMixin


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    # Un CUIT identifica a un sujeto, y dos fichas del mismo sujeto parten su historia en dos:
    # la mitad de los comprobantes queda en una y la mitad en la otra, y `get_by_tax_id` (que
    # resuelve el receptor de lo que llega de FactuMov y el proveedor de un PDF importado)
    # elige entre ellas sin criterio. El índice es parcial porque el contacto SIN CUIT es
    # legítimo y frecuente —el consumidor final, la persona a la que no se le factura— y de
    # esos tiene que poder haber muchos.
    __table_args__ = (
        Index(
            "uq_contacts_tax_id",
            "tax_id",
            unique=True,
            postgresql_where=text("tax_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trade_name: Mapped[str | None] = mapped_column(String(150))
    name: Mapped[str] = mapped_column(String(150))
    condicion_iva: Mapped[CondicionIva] = mapped_column(Enum(CondicionIva))
    doc_type: Mapped[DocType] = mapped_column(Enum(DocType))
    tax_id: Mapped[str | None] = mapped_column(String(11))
    contact_type: Mapped[ContactType] = mapped_column(Enum(ContactType))
    email: Mapped[str | None] = mapped_column(String(254))
    address: Mapped[str | None] = mapped_column(String(200))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="contact")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="contact")
    import_rules: Mapped[list["ImportRule"]] = relationship(back_populates="contact")
