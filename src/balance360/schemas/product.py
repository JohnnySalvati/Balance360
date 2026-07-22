import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    name: str
    margin: Decimal | None = Decimal(0)
    track_serial: bool = False


class ProductUpdate(BaseModel):
    name: str | None = None
    margin: Decimal | None = None
    track_serial: bool = False


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    margin: Decimal
    track_serial: bool = False
    created_at: datetime
    updated_at: datetime
