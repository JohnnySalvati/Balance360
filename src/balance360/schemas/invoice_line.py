import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, model_validator

class InvoiceLineCreate(BaseModel):
    invoice_id: uuid.UUID
    product_id: uuid.UUID|None=None
    description: str|None=None
    quantity: int
    unit_price: Decimal
    @model_validator(mode='after')
    def check_description(self) -> 'InvoiceLineCreate':
        if not self.product_id and not self.description:
            raise ValueError("Debe existir un producto o una descripcion")
        return self
    
class InvoiceLineUpdate(BaseModel):
    invoice_id: uuid.UUID|None=None
    product_id: uuid.UUID|None=None
    description: str|None=None
    quantity: int|None=None
    unit_price: Decimal|None=None

class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    invoice_id: uuid.UUID
    product_id: uuid.UUID|None=None
    description: str|None=None
    quantity: int
    unit_price: Decimal
    created_at: datetime
    updated_at: datetime