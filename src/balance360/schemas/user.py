import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class UserBase(BaseModel):
    email: str
    full_name: str
    is_active: bool

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class UserUpdate(BaseModel):
    email: str|None = None
    full_name: str|None = None
    is_active: bool|None = None
