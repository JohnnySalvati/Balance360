import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from balance360.models.account import AccountType
class AccountBase(BaseModel):
    name: str
    type: AccountType
    currency_code: str
    is_active: bool
class AccountCreate(AccountBase):
    pass
class AccountRead(AccountBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
class AccountUpdate(BaseModel):
    name: str|None = None
    type: AccountType|None = None
    currency_code: str|None = None
    is_active: bool|None = None
class AccountShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str