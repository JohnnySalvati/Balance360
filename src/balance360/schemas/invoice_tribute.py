import uuid
from decimal import Decimal

from pydantic import BaseModel

from balance360.enums import TributeType


class InvoiceTributeCreate(BaseModel):
    invoice_id: uuid.UUID
    tribute_type: TributeType
    description: str
    base_amount: Decimal
    rate: Decimal
