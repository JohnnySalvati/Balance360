import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from balance360.enums import CondicionIva
from balance360.services.text import digits_only


class EntityCreate(BaseModel):
    name: str

class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str

    created_at: datetime
    updated_at: datetime


class EntityUpdate(BaseModel):
    name: str | None = None

class EntityShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
