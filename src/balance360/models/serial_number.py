from typing import TYPE_CHECKING
import uuid


from sqlalchemy import Uuid, ForeignKey, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.models.base import Base, TimestampMixin
from balance360.enums import SerialStatus

if TYPE_CHECKING:
    from balance360.models.product import Product
    from balance360.models.invoice_line import InvoiceLine

class SerialNumber(Base, TimestampMixin):
    __tablename__ = "serial_numbers"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id")
    )
    serial: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )
    status: Mapped[SerialStatus] = mapped_column(
        Enum(SerialStatus)
    )
    purchase_line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invoice_lines.id")
    )
    sale_line_id: Mapped[uuid.UUID|None] = mapped_column(
        Uuid,
        ForeignKey("invoice_lines.id", ondelete="SET NULL"),
        nullable=True
    )
    product: Mapped['Product'] = relationship(
        back_populates="serial_numbers"
    )
    purchase_line: Mapped['InvoiceLine'] = relationship(
        foreign_keys=[purchase_line_id],
        back_populates="purchased_serials"
    )
    sale_line: Mapped['InvoiceLine|None'] = relationship(
        foreign_keys=[sale_line_id],
        back_populates="sold_serials"
    )
    