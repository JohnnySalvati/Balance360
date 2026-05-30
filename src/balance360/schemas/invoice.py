import uuid
import datetime
from pydantic import BaseModel, ConfigDict, model_validator
from balance360.enums import InvoiceType, VoucherType


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
    confirmed: bool=False
    paid: bool=False
    authorized: bool=False
    cae: str|None = None
    cae_expiry: datetime.date|None= None

    @model_validator(mode="after")
    def check_number(self):
        if self.formal:
            if not self.pos:
                raise ValueError("Se necesita punto de venta")

            if self.invoice_type == InvoiceType.purchase and not self.number:
                raise ValueError("Se necesita numero de comprobante")

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
    confirmed: bool|None=None
    paid: bool|None=None
    authorized: bool|None=None
    cae: str|None = None
    cae_expiry: datetime.date|None= None
    
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
    confirmed: bool=False
    paid: bool=False
    authorized: bool=False
    cae: str|None = None
    cae_expiry: datetime.date|None= None
    created_at: datetime.datetime
    updated_at: datetime.datetime

