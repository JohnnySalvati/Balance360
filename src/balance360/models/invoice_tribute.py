import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.enums import TributeType
from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.invoice import Invoice
from balance360.models.money import money


class InvoiceTribute(Base, TimestampMixin):
    __tablename__ = "invoice_tributes"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="CASCADE")
    )
    tribute_type: Mapped[TributeType] = mapped_column(Enum(TributeType))
    description: Mapped[str] = mapped_column(String(60))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2))
    rate: Mapped[Decimal] = mapped_column(Numeric(precision=8, scale=2))
    invoice: Mapped["Invoice"] = relationship(back_populates="invoice_tributes")

    @property
    def amount(self) -> Decimal:
        return money(self.base_amount * self.rate / 100)
