from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils.timezone import make_aware
from datetime import datetime

from apps.finance.models import Transaction, Category


def create_transfer(
    *,
    date: datetime,
    entity,
    from_account,
    to_account,
    amount: Decimal,
    description: str = "",
):
    if from_account == to_account:
        raise ValueError("La cuenta origen y destino no pueden ser la misma.")

    if amount <= 0:
        raise ValueError("El monto debe ser mayor a cero.")

    transfer_category = Category.objects.get(name="Transferencia interna")

    aware_date = make_aware(date) if date.tzinfo is None else date

    with db_transaction.atomic():
        # Egreso (origen)
        tx_out = Transaction(
            date=aware_date,
            entity=entity,
            account=from_account,
            category=transfer_category,
            direction=Transaction.OUT,
            amount=amount,
            description=description or f"Transferencia a {to_account.name}",
        )
        tx_out.clean()  # respeta cierres
        tx_out.save()

        # Ingreso (destino)
        tx_in = Transaction(
            date=aware_date,
            entity=entity,
            account=to_account,
            category=transfer_category,
            direction=Transaction.IN,
            amount=amount,
            description=description or f"Transferencia desde {from_account.name}",
        )
        tx_in.clean()  # respeta cierres
        tx_in.save()

    return tx_out, tx_in
