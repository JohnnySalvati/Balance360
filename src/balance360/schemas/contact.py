import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from balance360.enums import CondicionIva, ContactType, DocType
from balance360.services.text import digits_only


class ContactBase(BaseModel):
    name: str
    trade_name: str | None = None
    tax_id: str | None = None
    contact_type: ContactType
    condicion_iva: CondicionIva
    doc_type: DocType
    email: str | None = None
    address: str | None = None


class ContactCreate(ContactBase):
    pass

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, v: str) -> str | None:
        tax_id = None if v is None else digits_only(v)
        return tax_id


class ContactRead(ContactBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ContactUpdate(BaseModel):
    name: str | None = None
    trade_name: str | None = None
    tax_id: str | None = None
    contact_type: ContactType | None = None
    condicion_iva: CondicionIva | None = None
    doc_type: DocType | None = None
    email: str | None = None
    address: str | None = None

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, v: str) -> str | None:
        tax_id = None if v is None else digits_only(v)
        return tax_id


class ContactShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
