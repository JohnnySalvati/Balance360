from balance360.services.wsfe import get_last_voucher_number
from balance360.enums import VoucherType
from balance360.services.arca import get_access_ticket

ticket = get_access_ticket("wsfe")

response = get_last_voucher_number(
    cuit=20182810674,
    pos= 4,
    voucher_type=VoucherType.A,
    token=ticket["token"],
    sign=ticket["sign"]
)

print(response)
