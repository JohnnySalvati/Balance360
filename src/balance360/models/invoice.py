from typing import TYPE_CHECKING
import uuid
import datetime
from decimal import Decimal
from dataclasses import dataclass
from sqlalchemy import Uuid, Enum, Date, ForeignKey, Boolean, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.enums import InvoiceType, VoucherType, IvaAliquot
from balance360.models.base import Base, TimestampMixin
from balance360.enums import DocType, SerialStatus

if TYPE_CHECKING:
    from balance360.models.entity import Entity
    from balance360.models.contact import Contact
    from balance360.models.invoice_line import InvoiceLine
    from balance360.models.category import Category
    from balance360.models.transaction import Transaction
    from balance360.models.invoice_tribute import InvoiceTribute

class InvoiceAuthorizationError(Exception):
    pass
class InvoicePaymentError(Exception):
    pass
class InvoiceConfirmationError(Exception):
    pass
class InvoiceDeleteError(Exception):
    pass
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
    confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    paid: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    authorized: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
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
        back_populates="invoice", cascade="all, delete-orphan"
    )
    invoice_tributes: Mapped[list['InvoiceTribute']] = relationship(
        back_populates='invoice', cascade="all, delete-orphan"
    )
    transaction: Mapped['Transaction|None'] = relationship(
        back_populates="invoice"
    )

    @dataclass
    class IvaBreakdown:
        aliquot: IvaAliquot
        net_amount: Decimal
        iva_amount: Decimal

    @property
    def iva_breakdown(self) -> list[IvaBreakdown]:
        iva_aliquots = {}
        for line in self.invoice_lines:
            current = iva_aliquots.get(line.iva_aliquot, (Decimal(0), Decimal(0)))
            iva_aliquots[line.iva_aliquot] = (
                current[0] + line.iva_aliquot.rate * line.net_amount / 100,
                current[1] + line.net_amount
            )
        return [self.IvaBreakdown(
            aliquot=key,
            iva_amount=value[0],
            net_amount=value[1] 
        ) for key, value in iva_aliquots.items()
        ]

    @property
    def total(self) -> Decimal:
        iva_breakdown = self.iva_breakdown
        net_amount = sum((iva_item.net_amount for iva_item in iva_breakdown), Decimal(0))
        iva = sum((iva_item.iva_amount for iva_item in iva_breakdown), Decimal(0))
        tributes = sum((tribute.amount for tribute in self.invoice_tributes), Decimal(0))
        return  net_amount + iva + tributes
    
    @property
    def net_total(self) -> Decimal:
        return sum((iva_item.net_amount for iva_item in self.iva_breakdown), Decimal(0))


    def validate_authorization(self):
        if not self.entity.tax_id:
            raise InvoiceAuthorizationError("La entidad no posee CUIT")
    
        if not self.pos or not self.voucher_type:
            raise InvoiceAuthorizationError("El tipo y punto de venta del comprobante son obligatorios")
    
        if self.contact.doc_type != DocType.FINAL and not self.contact.tax_id:
            raise InvoiceAuthorizationError("Se necesita numero de CUIT del cliente")

        if not self.confirmed:
            raise InvoiceAuthorizationError("El comprobante no esta confirmado")
        
        if self.authorized:
            raise InvoiceAuthorizationError("El comprobante ya esta autorizado")
        
        if self.invoice_type == InvoiceType.purchase:
            raise InvoiceAuthorizationError("No se puede autorizar una compra")

    def validate_confirmation(self):
        if self.confirmed:
            raise InvoiceConfirmationError("El comprobante ya esta confirmado")
        if not self.invoice_lines:
            raise InvoiceConfirmationError("El comprobante no tiene items")
        
        for invoice_line in self.invoice_lines:
            if not invoice_line.product or not invoice_line.product.track_serial:
                continue

            if self.invoice_type == InvoiceType.sale:
                if invoice_line.quantity != len(invoice_line.sold_serials):
                    raise InvoiceConfirmationError("Cantidad erronea de seriales")
                for serial in invoice_line.sold_serials:
                    if serial.product_id != invoice_line.product_id:
                        raise InvoiceConfirmationError("El serial no corresponde a este producto")
                    if serial.status != SerialStatus.reserved:
                        raise InvoiceConfirmationError("El serial no esta reservado")
            else:
                if invoice_line.quantity != len(invoice_line.purchased_serials):
                    raise InvoiceConfirmationError("Cantidad erronea de seriales")
                for serial in invoice_line.purchased_serials:
                    if serial.product_id != invoice_line.product_id:
                        raise InvoiceConfirmationError("El serial no corresponde a este producto")
                    if serial.status != SerialStatus.pending:
                        raise InvoiceConfirmationError("El serial no esta pendiente")
                

    def validate_payment(self):
        if not self.confirmed:
            raise InvoicePaymentError("El comprobante no esta confirmado")
        if self.paid:
            raise InvoicePaymentError("El comprobante ya esta pago")
        
    def validate_delete(self):
        if self.confirmed:
            raise InvoiceDeleteError("El comprobante esta confirmado")