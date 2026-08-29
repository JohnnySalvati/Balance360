import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ColumnElement,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.enums import Concepto, InvoiceType, IvaAliquot, VoucherType
from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.attachment import Attachment
    from balance360.models.category import Category
    from balance360.models.contact import Contact
    from balance360.models.entity import Entity
    from balance360.models.fiscal_identity import FiscalIdentity
    from balance360.models.invoice_line import InvoiceLine
    from balance360.models.invoice_tribute import InvoiceTribute
    from balance360.models.transaction import Transaction
from balance360.models.money import money


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("external_source", "external_id", name="uq_invoices_external"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_type: Mapped[InvoiceType] = mapped_column(Enum(InvoiceType))
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"))
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    date: Mapped[datetime.date] = mapped_column(Date)
    formal: Mapped[bool] = mapped_column(Boolean, default=True)
    tax_only: Mapped[bool] = mapped_column(Boolean, default=False)
    voucher_type: Mapped[VoucherType | None] = mapped_column(Enum(VoucherType))
    pos: Mapped[int | None] = mapped_column(Integer)
    number: Mapped[int | None] = mapped_column(Integer)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    authorized: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cae: Mapped[str | None] = mapped_column(String(14))
    cae_expiry: Mapped[datetime.date | None] = mapped_column(Date)
    concepto: Mapped[Concepto] = mapped_column(
        Enum(Concepto), default=Concepto.products, server_default=Concepto.products.name
    )
    from_date: Mapped[datetime.date | None] = mapped_column(Date)
    to_date: Mapped[datetime.date | None] = mapped_column(Date)
    due_date: Mapped[datetime.date | None] = mapped_column(Date)
    fiscal_identity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fiscal_identities.id"))
    related_invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"))
    # De dónde vino, cuando no se cargó acá. `None` = lo cargó alguien en esta app; "factumov"
    # = lo emitió FactuMov y esto es su registro contable.
    #
    # Las dos columnas juntas son la **clave de idempotencia** de la integración, y esa es toda
    # su razón de ser: registrar es un POST que se reintenta —FactuMov reintenta solo cuando
    # esto no contesta— y sin una clave estable el segundo intento duplica un comprobante que
    # ya no se puede borrar sin romperle la numeración a nada. Con el índice único, el
    # reintento choca contra la fila que ya está y devuelve esa.
    external_source: Mapped[str | None] = mapped_column(String(20))
    external_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    entity: Mapped["Entity"] = relationship(back_populates="invoices", order_by="Entity.name")
    contact: Mapped["Contact"] = relationship(back_populates="invoices", order_by="Contact.name")
    category: Mapped["Category|None"] = relationship(
        back_populates="invoices", order_by="Category.name"
    )
    invoice_lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLine.created_at"
    )
    invoice_tributes: Mapped[list["InvoiceTribute"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    transaction: Mapped["Transaction|None"] = relationship(
        back_populates="invoice", order_by="Transaction.date"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    fiscal_identity: Mapped["FiscalIdentity | None"] = relationship(back_populates="invoices")
    related_invoice: Mapped["Invoice | None"] = relationship(
        "Invoice", remote_side=[id], back_populates="related_credit_notes"
    )
    related_credit_notes: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="related_invoice"
    )

    @dataclass
    class IvaBreakdown:
        aliquot: IvaAliquot
        net_amount: Decimal
        iva_amount: Decimal

    @property
    def iva_breakdown(self) -> list[IvaBreakdown]:
        results = {}
        for line in self.invoice_lines:
            net_amount, iva_amount = results.get(line.iva_aliquot, (Decimal(0), Decimal(0)))
            if self.discriminates_iva:
                results[line.iva_aliquot] = (
                    net_amount + money(line.net_amount),
                    iva_amount + money(line.iva_rate * line.net_amount / 100),
                )
            elif self.applies_iva:
                derived_net = money(line.gross_amount / (1 + line.iva_rate / 100))
                results[line.iva_aliquot] = (
                    net_amount + derived_net,
                    iva_amount + money(line.gross_amount - derived_net),
                )
            else:
                results[line.iva_aliquot] = (net_amount + money(line.net_amount), Decimal(0))
        return [
            self.IvaBreakdown(aliquot=key, net_amount=value[0], iva_amount=value[1])
            for key, value in results.items()
        ]

    @property
    def total(self) -> Decimal:
        iva_breakdown = self.iva_breakdown
        net_amount = sum((iva_item.net_amount for iva_item in iva_breakdown), Decimal(0))
        iva = sum((iva_item.iva_amount for iva_item in iva_breakdown), Decimal(0))
        tributes = sum((tribute.amount for tribute in self.invoice_tributes), Decimal(0))
        return net_amount + iva + tributes

    @property
    def net_total(self) -> Decimal:
        return sum((iva_item.net_amount for iva_item in self.iva_breakdown), Decimal(0))

    @property
    def discriminates_iva(self) -> bool:
        return self.voucher_type in (VoucherType.A, VoucherType.NCA)

    @property
    def is_nc(self) -> bool:
        return self.voucher_type in (VoucherType.NCA, VoucherType.NCB, VoucherType.NCC)

    @hybrid_property
    def applies_iva(self) -> bool:
        return self.voucher_type not in (VoucherType.C, VoucherType.NCC)

    @applies_iva.inplace.expression
    @classmethod
    def _applies_iva_expression(cls) -> ColumnElement[bool]:
        return cls.voucher_type.notin_([VoucherType.C, VoucherType.NCC])

    @property
    def is_printable(self) -> bool:
        return bool(self.authorized and self.cae and self.fiscal_identity)
