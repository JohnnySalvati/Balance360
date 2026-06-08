from decimal import Decimal
from pydantic import BaseModel

class AppconfigUpdate(BaseModel):
    import_rule_tolerance_pct: Decimal|None = None