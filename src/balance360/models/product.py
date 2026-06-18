import uuid
from decimal import Decimal
from sqlalchemy import Uuid, String, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from balance360.models.serial_number import SerialNumber
    from balance360.models.invoice_line import InvoiceLine
    
from balance360.models.base import Base, TimestampMixin

class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(100)
    )
    margin: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2)
    )
    track_serial: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    
    serial_numbers: Mapped[list['SerialNumber']] = relationship(
        back_populates="product"
    )
    invoice_lines: Mapped[list['InvoiceLine']] = relationship(
        back_populates="product"
    )
    