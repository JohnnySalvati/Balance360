import uuid

from pydantic import BaseModel

from balance360.enums import SerialStatus


class SerialNumberCreate(BaseModel):
    product_id: uuid.UUID
    serial: str
    purchase_line_id: uuid.UUID
    status: SerialStatus = SerialStatus.available


class SerialNumberUpdate(BaseModel):
    product_id: uuid.UUID | None = None
    serial: str | None = None
    purchase_line_id: uuid.UUID | None = None
    sale_line_id: uuid.UUID | None = None
    status: SerialStatus | None = None
