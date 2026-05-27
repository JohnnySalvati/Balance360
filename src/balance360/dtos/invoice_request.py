import datetime
from decimal import Decimal
from pydantic import BaseModel
from balance360.dtos.auth import Auth
from balance360.enums import VoucherType

class VoucherData(BaseModel):
    date: datetime.date
    receiver_doc_type: str
    receiver_doc_number: str
    total: Decimal

class VoucherInfo(BaseModel):
    pos: int
    voucher_type: VoucherType
    number: int

class InvoiceRequest(BaseModel):
    auth: Auth
    voucher_info: VoucherInfo
    voucher_data: VoucherData
