import uuid
from datetime import datetime
from balance360.enums import ContactType, CondicionIva, DocType
from pydantic import BaseModel, ConfigDict

class ContactBase(BaseModel):
    name: str
    tax_id: str|None = None
    contact_type: ContactType
    condicion_iva: CondicionIva
    doc_type: DocType
    email: str|None = None

class ContactCreate(ContactBase):
    pass

class ContactRead(ContactBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class ContactUpdate(BaseModel):
    name: str|None = None
    tax_id: str|None = None
    contact_type: ContactType|None = None
    condicion_iva: CondicionIva|None = None
    doc_type: DocType|None = None
    email: str|None = None

class ContactShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


