import uuid
import datetime
from decimal import Decimal
from pydantic import BaseModel
from balance360.enums import ImportRowStatus

class ImportRowCreate(BaseModel):
    batch_id: uuid.UUID
    account_id: uuid.UUID
    source_row: int
    date: datetime.date|None=None
    description: str
    debit: Decimal|None=None
    credit: Decimal|None=None
    status: ImportRowStatus
    reason: str
    
