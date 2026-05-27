from typing import TYPE_CHECKING
import uuid
import datetime
from decimal import Decimal
from sqlalchemy import Uuid, Enum, Date, ForeignKey, Boolean, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.enums import InvoiceType, VoucherType, VoucherStatus, IvaAliquot
from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.entity import Entity
    from balance360.models.contact import Contact
    from balance360.models.invoice_line import InvoiceLine
    from balance360.models.category import Category
    from balance360.models.transaction import Transaction
    from balance360.models.invoice_tribute import InvoiceTribute

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
        ForeignKey("categories.id")
    )
    date: Mapped[datetime.date] = mapped_column(
        Date
    )
    formal: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    tax_only: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    voucher_type: Mapped[VoucherType|None] = mapped_column(
        Enum(VoucherType)
    )
    pos: Mapped[int|None] = mapped_column(
        Integer
    )
    number: Mapped[int|None] = mapped_column(
        Integer
    )
    status: Mapped[VoucherStatus]= mapped_column(
        Enum(VoucherStatus), default=VoucherStatus.pending
    )
    cae: Mapped[str|None] = mapped_column(
        String(14)
    )
    cae_expiry: Mapped[datetime.date|None] = mapped_column(
        Date
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
    invoice_tributes: Mapped[list['InvoiceTribute']] = relationship(
        back_populates='invoice'
    )
    transaction: Mapped['Transaction|None'] = relationship(
        back_populates="invoice"
    )

    @property
    def iva_breakdown(self) -> dict[IvaAliquot, Decimal]:
        iva_aliquots = {}
        for line in self.invoice_lines:
            iva_aliquots[line.iva_aliquot] = (
                iva_aliquots.get(line.iva_aliquot, Decimal(0)) + 
                line.iva_aliquot.rate * line.quantity * line.unit_price / 100
            )
        return iva_aliquots

    @property
    def total(self) -> Decimal:
        net_amount = sum((line.net_amount for line in self.invoice_lines), Decimal(0))
        iva = sum((iva_item_value for __, iva_item_value in self.iva_breakdown.items()), Decimal(0))
        tributes = sum((tribute.amount for tribute in self.invoice_tributes), Decimal(0))
        return  net_amount + iva + tributes