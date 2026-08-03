import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EntityCreate(BaseModel):
    name: str
    fiscal_identity_ids: list[uuid.UUID] = []


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    fiscal_identity_ids: list[uuid.UUID]

    created_at: datetime
    updated_at: datetime


class EntityUpdate(BaseModel):
    name: str | None = None
    fiscal_identity_ids: list[uuid.UUID] = []


class EntityShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
