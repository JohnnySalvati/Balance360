import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from balance360.enums import CondicionIva

class EntityBase(BaseModel):
    name: str
    tax_id: str|None = None
    condicion_iva: CondicionIva

class EntityCreate(EntityBase):
    pass

class EntityRead(EntityBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class EntityUpdate(BaseModel):
    name: str|None = None
    tax_id: str|None = None
    condicion_iva: CondicionIva|None = None

class EntityShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str