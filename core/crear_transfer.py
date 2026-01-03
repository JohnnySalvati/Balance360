from apps.finance.services.transfers import create_transfer
from apps.finance.models import Account, EconomicEntity

# create_transfer(
#     from_account=Account.objects.get(name="Efectivo"),
#     to_account=Account.objects.get(name="Banco Ciudad"),
#     entity=EconomicEntity.objects.get(name__icontains="InSoft"),
#     amount=50000,
# )
