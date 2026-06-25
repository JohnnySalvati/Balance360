import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from balance360.enums import CondicionIva



class EntityCreate(BaseModel):
    name: str
    tax_id: str|None = None
    condicion_iva: CondicionIva
    iibb_rate: Decimal = Decimal(0)
    
class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    tax_id: str|None = None
    condicion_iva: CondicionIva
    created_at: datetime
    updated_at: datetime

class EntityUpdate(BaseModel):
    name: str|None = None
    tax_id: str|None = None
    condicion_iva: CondicionIva|None = None
    iibb_rate: Decimal|None=None

class EntityShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str

