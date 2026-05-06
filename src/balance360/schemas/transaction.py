import uuid
import decimal
import datetime
from pydantic import BaseModel, ConfigDict, model_validator
from balance360.enums import TransactionType   
from balance360.schemas.account import AccountShort
from balance360.schemas.entity import EntityShort
from balance360.schemas.currency import CurrencyShort
from balance360.schemas.contact import ContactShort
from balance360.schemas.category import CategoryShort
class TransactionCreate(BaseModel):
    date: datetime.date
    description: str
    amount: decimal.Decimal
    type: TransactionType
    from_account_id: uuid.UUID|None=None
    to_account_id: uuid.UUID|None=None
    entity_id: uuid.UUID|None=None
    currency_id: uuid.UUID
    contact_id: uuid.UUID|None=None
    category_id: uuid.UUID|None=None

    @model_validator(mode='after')
    def check_type(self) -> 'TransactionCreate':
        if self.type == TransactionType.income and (self.from_account_id is not None or self.to_account_id is None):
            raise ValueError("Los ingresos deben tener una cuenta destino y no tener cuenta origen")
        if self.type == TransactionType.expense and (self.from_account_id is None or self.to_account_id is not None):
            raise ValueError("Los egresos no deben tener una cuenta destino y deben tener una cuenta origen")
        if self.type == TransactionType.transfer and (self.from_account_id is None or self.to_account_id is None):
            raise ValueError("Las transferencias deben tener una cuenta origen y una destino")
        return self
class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    date: datetime.date
    description: str
    amount: decimal.Decimal
    type: TransactionType
    from_account: AccountShort|None=None
    to_account: AccountShort|None=None
    entity: EntityShort|None=None
    currency: CurrencyShort
    contact: ContactShort|None=None
    category: CategoryShort|None=None
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
