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


def _normalize_tax_id(v: str | None) -> str | None:
    """Deja solo los dígitos, y la cadena vacía la convierte en NULL.

    El `or None` es lo que sostiene el índice único parcial de `contacts`: en Postgres
    varios NULL conviven, pero varias cadenas vacías no. Sin esto, el segundo contacto sin
    CUIT cargado por un camino que manda `""` en vez de omitir el campo —la API JSON, el
    alta rápida desde una factura— rebotaría contra el índice diciendo que el CUIT está
    repetido, que es justo lo que no pasa.
    """
    return digits_only(v) or None


class ContactCreate(ContactBase):
    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, v: str | None) -> str | None:
        return _normalize_tax_id(v)


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
    def validate_tax_id(cls, v: str | None) -> str | None:
        return _normalize_tax_id(v)


class ContactShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
