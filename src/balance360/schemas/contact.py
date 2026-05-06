import uuid
from datetime import datetime
from balance360.enums import ContactType
from pydantic import BaseModel, ConfigDict

class ContactBase(BaseModel):
    name: str
    is_active: bool = True
    tax_id: str | None = None
    contact_type : ContactType
class ContactCreate(ContactBase):
    pass
class ContactRead(ContactBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
class ContactUpdate(BaseModel):
    name: str|None = None
    is_active: bool|None = None
    tax_id: str|None = None
    contact_type: ContactType|None = None
class ContactShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


