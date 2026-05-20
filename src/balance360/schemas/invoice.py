import uuid
import datetime
from pydantic import BaseModel, ConfigDict, model_validator
from balance360.enums import InvoiceType, VoucherType, VoucherStatus


class InvoiceCreate(BaseModel):
    invoice_type: InvoiceType
    entity_id: uuid.UUID
    contact_id: uuid.UUID
    category_id: uuid.UUID|None=None
    date: datetime.date
    formal: bool
    tax_only: bool
    voucher_type: VoucherType|None=None
    pos: int|None=None
    number: int|None=None
    
    @model_validator(mode='after')
    def check_formal(self) -> 'InvoiceCreate':
        if self.formal:
            if not (self.voucher_type and self.pos and self.number):
                raise ValueError('Todos los atributos son requeridos')
        return self
    
class InvoiceUpdate(BaseModel):
    invoice_type: InvoiceType|None=None
    entity_id: uuid.UUID|None=None
    contact_id: uuid.UUID|None=None
    category_id: uuid.UUID|None=None
    date: datetime.date|None=None
    formal: bool|None=None
    tax_only: bool|None=None
    voucher_type: VoucherType|None=None
    pos: int|None=None
    number: int|None=None
    
class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    invoice_type: InvoiceType
    entity_id: uuid.UUID
    contact_id: uuid.UUID
    category_id: uuid.UUID|None=None
    date: datetime.date
    formal: bool
    tax_only: bool
    voucher_type: VoucherType|None=None
    pos: int|None=None
    number: int|None=None
    status: VoucherStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime

