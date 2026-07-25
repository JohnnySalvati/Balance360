import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
