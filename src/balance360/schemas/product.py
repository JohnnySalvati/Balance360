from pydantic import BaseModel, ConfigDict
import uuid
from decimal import Decimal
from datetime import datetime

class ProductCreate(BaseModel):
    name: str
    margin: Decimal|None = Decimal(0)

class ProductUpdate(BaseModel):
    name: str|None = None
    margin: Decimal|None = None

class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    margin: Decimal
    created_at: datetime
    updated_at: datetime



