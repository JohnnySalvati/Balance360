import uuid
import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
class ExchangeRateBase(BaseModel):
    currency_id: uuid.UUID
    date: datetime.date
    rate: Decimal
class ExchangeRateRead(ExchangeRateBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
class ExchangeRateCreate(ExchangeRateBase):
    pass 
class ExchangeRateUpdate(BaseModel):
    currency_id: uuid.UUID|None = None
    date: datetime.date|None = None
    rate: Decimal|None = None
