import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    is_active: bool

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class UserUpdate(BaseModel):
    email: str|None = None
    full_name: str|None = None
    is_active: bool|None = None
