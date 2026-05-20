import uuid
import decimal
import datetime
from pydantic import BaseModel, ConfigDict
from balance360.enums import TransactionType   
from balance360.schemas.account import AccountShort
from balance360.schemas.entity import EntityShort
from balance360.schemas.contact import ContactShort
from balance360.schemas.category import CategoryShort
from balance360.schemas.import_rule import ImportRuleShort
class TransactionCreate(BaseModel):
    date: datetime.date
    description: str
    amount: decimal.Decimal
    type: TransactionType
    account_id: uuid.UUID
    entity_id: uuid.UUID|None=None
    contact_id: uuid.UUID|None=None
    category_id: uuid.UUID|None=None
    invoice_id: uuid.UUID|None=None
    is_manual: bool=False
    is_transfer: bool=False
    applied_rule_id: uuid.UUID|None=None
class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    date: datetime.date
    description: str
    amount: decimal.Decimal
    type: TransactionType
    account: AccountShort
    entity: EntityShort|None=None
    contact: ContactShort|None=None
    category: CategoryShort|None=None
    invoice_id: uuid.UUID|None=None
    is_manual: bool
    is_transfer: bool
    applied_rule: ImportRuleShort|None=None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
class TransactionUpdate(BaseModel):
    date: datetime.date|None = None
    description: str|None = None
    amount: decimal.Decimal|None = None
    type: TransactionType|None = None
    account_id: uuid.UUID|None = None
    entity_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None
    invoice_id: uuid.UUID|None=None
    is_manual: bool|None = None
    is_transfer: bool|None = None
    applied_rule_id: uuid.UUID|None=None