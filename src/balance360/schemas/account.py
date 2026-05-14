import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from balance360.models.account import AccountType
from balance360.schemas.currency import CurrencyShort
class AccountBase(BaseModel):
    name: str
    type: AccountType
    currency_id: uuid.UUID
class AccountCreate(AccountBase):
    pass
class AccountRead(AccountBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    currency: CurrencyShort
    created_at: datetime
    updated_at: datetime
class AccountUpdate(BaseModel):
    name: str|None = None
    type: AccountType|None = None
    currency_id: uuid.UUID|None = None
class AccountShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str