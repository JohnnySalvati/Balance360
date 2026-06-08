import uuid
from decimal import Decimal
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
    transaction_type: TransactionType
    is_transfer: bool
    min_amount: Decimal
    max_amount: Decimal
    created_at: datetime
    updated_at: datetime

class ImportRuleCreate(BaseModel):
    pattern: str
    entity_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None
    transaction_type: TransactionType
    is_transfer: bool
    min_amount: Decimal
    max_amount: Decimal

    @model_validator(mode='after')
    def check_one_required(self) -> 'ImportRuleCreate':
        if not self.entity_id and not self.contact_id and not self.category_id and not self.is_transfer:
            raise ValueError('One attribute is required')
        if self.min_amount > self.max_amount:
            raise ValueError('min_amount greather than max_amount')
        return self
class ImportRuleUpdate(BaseModel):
    pattern: str|None = None
    entity_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None
    transaction_type: TransactionType|None = None
    is_transfer: bool|None = None
    min_amount: Decimal|None = None
    max_amount: Decimal|None = None


class ImportRuleShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    pattern: str
