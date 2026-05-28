from datetime import date
from decimal import Decimal
from balance360.services.wsfe import get_last_voucher_number, authorize_invoice
from balance360.enums import VoucherType, IvaAliquot, TributeType, CondicionIva, DocType
from balance360.services.arca import get_access_ticket
from balance360.dtos.invoice_request import InvoiceRequest, VoucherInfo, VoucherData, IvaDetail, Tribute
from balance360.dtos.auth import Auth
ticket = get_access_ticket("wsfe")
token = ticket["token"]
sign = ticket["sign"]

auth = Auth(cuit="20182810674", token=token, sign=sign)

voucher_info = VoucherInfo(pos=4, voucher_type=VoucherType.A)

iva_detail = [IvaDetail(id=IvaAliquot.standard.arca_code, base_imp=Decimal(10000), amount=Decimal(2100))]
tributes = [Tribute(id=TributeType.iibb.value, description="Ingresos Brutos CABA", base_imp=Decimal(10000), aliquot=Decimal(3),amount=Decimal(300))]
voucher_data = VoucherData(
    date=date.today(),
    receiver_condicion_iva=CondicionIva.INSCRIPTO,
    receiver_doc_type=DocType.CUIT,
    receiver_doc_number="30503218107",
    iva_detail=iva_detail,
    tributes=tributes,
    total=Decimal(12400)
    )

invoice_request = InvoiceRequest(
    auth=auth,
    voucher_info=voucher_info,
    voucher_data=voucher_data
    )

response = authorize_invoice(invoice_request)

print(response.cae, response.expiration)