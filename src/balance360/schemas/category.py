import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class CategoryBase(BaseModel):
    name: str
    parent_id: uuid.UUID|None = None
    description: str|None = None

class CategoryCreate(CategoryBase):
    pass

class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class CategoryUpdate(BaseModel):
    name: str|None = None
    parent_id: uuid.UUID|None = None
    description: str|None = None
