import uuid
import decimal
import datetime
from pydantic import BaseModel, ConfigDict
from balance360.enums import TransactionType   

class TransactionBase(BaseModel):
    date: datetime.date
    description: str
    amount: decimal.Decimal
    type: TransactionType
    from_account_id: uuid.UUID|None
    to_account_id: uuid.UUID|None
    entity_id: uuid.UUID|None
    currency_id: uuid.UUID
    contact_id: uuid.UUID|None
    category_id: uuid.UUID|None

class TransactionCreate(TransactionBase):
    pass 

class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

class TransactionUpdate(BaseModel):
    date: datetime.date|None = None
    description: str|None = None
    amount: decimal.Decimal|None = None
    type: TransactionType|None = None
    from_account_id: uuid.UUID|None = None
    to_account_id: uuid.UUID|None = None
    entity_id: uuid.UUID|None = None
    currency_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None

