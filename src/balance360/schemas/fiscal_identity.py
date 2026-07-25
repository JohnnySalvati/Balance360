import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from balance360.enums import CondicionIva
from balance360.services.text import digits_only


class FiscalIdentityCreate(BaseModel):
    entity_id: uuid.UUID
    name: str
    tax_id: str
    condicion_iva: CondicionIva
    iibb_rate: Decimal = Decimal(0)
    address: str
    iibb: str
    start_date: date

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, v: str) -> str | None:
        tax_id = None if v is None else digits_only(v)
        return tax_id


class FiscalIdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    tax_id: str | None = None
    condicion_iva: CondicionIva
    iibb_rate: Decimal = Decimal(0)
    address: str | None = None
    iibb: str | None = None
    start_date: date | None = None

    created_at: datetime
    updated_at: datetime


class FiscalIdentityUpdate(BaseModel):
    entity_id: uuid.UUID | None = None
    name: str | None = None
    tax_id: str | None = None
    condicion_iva: CondicionIva | None = None
    iibb_rate: Decimal | None = None
    address: str | None = None
    iibb: str | None = None
    start_date: date | None = None

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, v: str) -> str | None:
        tax_id = None if v is None else digits_only(v)
        return tax_id


class FiscalIdentityShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
