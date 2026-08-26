import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class EntityEmailIdentity(BaseModel):
    """Como se presenta la entidad en los mails que manda."""

    email_display_name: str | None = None
    email_reply_to: str | None = None
    email_signature: str | None = None

    @field_validator("email_display_name", "email_reply_to", "email_signature", mode="before")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        """Un input de texto vacio llega como "" y no como None.

        Sin esto la entidad guardaria cadenas vacias, y despues `entity.email_reply_to
        or algo` funcionaria de casualidad mientras que un `is not None` daria True
        para un campo que el usuario dejo en blanco.
        """
        if value is None:
            return None
        return value.strip() or None


class EntityCreate(EntityEmailIdentity):
    name: str
    fiscal_identity_ids: list[uuid.UUID] = []


class EntityRead(EntityEmailIdentity):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    fiscal_identity_ids: list[uuid.UUID]

    created_at: datetime
    updated_at: datetime


class EntityUpdate(EntityEmailIdentity):
    name: str | None = None
    fiscal_identity_ids: list[uuid.UUID] = []


class EntityShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
