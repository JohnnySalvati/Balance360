import uuid
from pydantic import BaseModel, model_validator, ConfigDict
from balance360.enums import TransactionType

class ImportRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    pattern: str
    entity_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None
    transaction_type: TransactionType
    applied: int

class ImportRuleCreate(BaseModel):
    pattern: str
    entity_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None
    transaction_type: TransactionType
    applied: int = 1

    @model_validator(mode='after')
    def check_one_required(self) -> 'ImportRuleCreate':
        if not self.entity_id and not self.contact_id and not self.category_id:
            raise ValueError('One attribute is required')
        return self

class ImportRuleUpdate(BaseModel):
    entity_id: uuid.UUID|None = None
    contact_id: uuid.UUID|None = None
    category_id: uuid.UUID|None = None
    transaction_type: TransactionType|None = None
    applied: int|None = None

