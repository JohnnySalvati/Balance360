import datetime
from decimal import Decimal

from pydantic import BaseModel

from balance360.dtos.auth import Auth
from balance360.enums import Concepto, CondicionIva, DocType, VoucherType


class IvaDetail(BaseModel):
    id: int
    base_imp: Decimal
    amount: Decimal


class Tribute(BaseModel):
    id: int
    description: str
    base_imp: Decimal
    aliquot: Decimal
    amount: Decimal


class AssociatedVoucher(BaseModel):
    tipo: int
    pos: int
    number: int
    cuit: int
    date: datetime.date


class VoucherData(BaseModel):
    date: datetime.date
    receiver_condicion_iva: CondicionIva
    receiver_doc_type: DocType
    receiver_doc_number: int
    iva_detail: list[IvaDetail] | None
    tributes: list[Tribute]
    total: Decimal
    concepto: Concepto
    from_date: datetime.date | None
    to_date: datetime.date | None
    due_date: datetime.date | None
    associated_vouchers: list[AssociatedVoucher] = []


class VoucherInfo(BaseModel):
    pos: int
    voucher_type: VoucherType


class InvoiceRequest(BaseModel):
    auth: Auth
    voucher_info: VoucherInfo
    voucher_data: VoucherData
