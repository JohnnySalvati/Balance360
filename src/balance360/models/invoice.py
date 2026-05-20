from typing import TYPE_CHECKING
import uuid
import datetime
from decimal import Decimal
from sqlalchemy import Uuid, Enum, Date, ForeignKey, Boolean, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.enums import InvoiceType, VoucherType, VoucherStatus
from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.entity import Entity
    from balance360.models.contact import Contact
    from balance360.models.invoice_line import InvoiceLine
    from balance360.models.category import Category
    from balance360.models.transaction import Transaction

class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    invoice_type: Mapped[InvoiceType] = mapped_column(
        Enum(InvoiceType)
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id")
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id")
    )
    category_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False
    )
    formal: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    tax_only: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    voucher_type: Mapped[VoucherType|None] = mapped_column(
        Enum(VoucherType), nullable=True
    )
    pos: Mapped[int|None] = mapped_column(
        Integer, nullable=True
    )
    number: Mapped[int|None] = mapped_column(
        Integer, nullable=True
    )
    status: Mapped[VoucherStatus]= mapped_column(
        Enum(VoucherStatus), default=VoucherStatus.pending
    )
    entity: Mapped['Entity'] = relationship(
        back_populates="invoices"
    )
    contact: Mapped['Contact'] = relationship(
        back_populates="invoices"
    )
    category: Mapped['Category|None'] = relationship(
        back_populates='invoices'
    )
    invoice_lines: Mapped[list['InvoiceLine']] = relationship(
        back_populates="invoice"
    )
    transaction: Mapped['Transaction|None'] = relationship(
        back_populates="invoice"
    )

    @property
    def total(self) -> Decimal:
        return sum((line.quantity * line.unit_price for line in self.invoice_lines), Decimal(0))