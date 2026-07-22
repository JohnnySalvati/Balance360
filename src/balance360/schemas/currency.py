import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CurrencyBase(BaseModel):
    code: str
    name: str
    is_bond: bool = False
    is_index: bool = False


class CurrencyCreate(CurrencyBase):
    pass


class CurrencyRead(CurrencyBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CurrencyUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    is_bond: bool | None = None
    is_index: bool | None = None


class CurrencyShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
