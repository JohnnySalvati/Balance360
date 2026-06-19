import uuid
from pydantic import BaseModel, model_validator, ConfigDict
from balance360.enums import TransactionType
from datetime import datetime
class ImportRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    pattern: str
    entity_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None
    account_id: uuid.UUID|None = None
    transaction_type: TransactionType
    is_transfer: bool
    created_at: datetime
    updated_at: datetime

class ImportRuleCreate(BaseModel):
    pattern: str
    entity_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None
    account_id: uuid.UUID|None = None
    transaction_type: TransactionType
    is_transfer: bool

    @model_validator(mode='after')
    def check_one_required(self) -> 'ImportRuleCreate':
        if not any([self.entity_id, self.contact_id, self.category_id, self.account_id, self.is_transfer]):
            raise ValueError('One attribute is required')
        return self
class ImportRuleUpdate(BaseModel):
    pattern: str|None = None
    entity_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None
    account_id: uuid.UUID|None = None
    transaction_type: TransactionType|None = None
    is_transfer: bool|None = None


class ImportRuleShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    pattern: str
