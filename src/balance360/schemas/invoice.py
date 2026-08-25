import datetime
import uuid

from pydantic import BaseModel, ConfigDict, model_validator

from balance360.enums import Concepto, InvoiceType, VoucherType


class InvoiceCreate(BaseModel):
    invoice_type: InvoiceType
    entity_id: uuid.UUID
    fiscal_identity_id: uuid.UUID | None = None
    contact_id: uuid.UUID
    category_id: uuid.UUID | None = None
    date: datetime.date
    formal: bool
    tax_only: bool
    voucher_type: VoucherType | None = None
    pos: int | None = None
    number: int | None = None
    confirmed: bool = False
    paid: bool = False
    authorized: bool = False
    cae: str | None = None
    cae_expiry: datetime.date | None = None
    concepto: Concepto = Concepto.products
    from_date: datetime.date | None = None
    to_date: datetime.date | None = None
    due_date: datetime.date | None = None
    related_invoice_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.concepto is not Concepto.products:
            if not (self.from_date and self.to_date and self.due_date):
                raise ValueError("Fecha desde, hasta y vencimiento son obligatorias")
            if self.from_date > self.to_date:
                raise ValueError("La fecha desde no puede ser mayor que la fecha hasta")
            if self.due_date < self.date:
                raise ValueError(
                    "La fecha de vencimiento debe ser mayor o igual a la fecha del comprobante"
                )
        return self


class InvoiceUpdate(BaseModel):
    invoice_type: InvoiceType | None = None
    entity_id: uuid.UUID | None = None
    fiscal_identity_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    date: datetime.date | None = None
    formal: bool | None = None
    tax_only: bool | None = None
    voucher_type: VoucherType | None = None
    pos: int | None = None
    number: int | None = None
    confirmed: bool | None = None
    paid: bool | None = None
    authorized: bool | None = None
    cae: str | None = None
    cae_expiry: datetime.date | None = None
    concepto: Concepto | None = None
    from_date: datetime.date | None = None
    to_date: datetime.date | None = None
    due_date: datetime.date | None = None
    related_invoice_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.concepto is not None and self.concepto is not Concepto.products:
            if not (self.from_date and self.to_date and self.due_date):
                raise ValueError("Fecha desde, hasta y vencimiento son obligatorias")
            if self.from_date > self.to_date:
                raise ValueError("La fecha desde no puede ser mayor que la fecha hasta")
            if self.date and self.due_date < self.date:
                raise ValueError(
                    "La fecha de vencimiento debe ser mayor o igual a la fecha del comprobante"
                )
        return self


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    invoice_type: InvoiceType
    entity_id: uuid.UUID
    fiscal_identity_id: uuid.UUID | None = None
    contact_id: uuid.UUID
    category_id: uuid.UUID | None = None
    date: datetime.date
    formal: bool
    tax_only: bool
    voucher_type: VoucherType | None = None
    pos: int | None = None
    number: int | None = None
    confirmed: bool = False
    paid: bool = False
    authorized: bool = False
    cae: str | None = None
    cae_expiry: datetime.date | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
