from django.db import transaction as db_transaction
from django.utils.timezone import now

from apps.finance.models import Transaction, Category


def create_transfer(
    *,
    from_account,
    to_account,
    entity,
    amount,
    description=""
):
    if from_account == to_account:
        raise ValueError("La cuenta origen y destino no pueden ser la misma.")

    if amount <= 0:
        raise ValueError("El monto debe ser mayor a cero.")

    category = Category.objects.get(name="Transferencia interna")

    with db_transaction.atomic():
        # Egreso
        Transaction.objects.create(
            account=from_account,
            entity=entity,
            category=category,
            amount=amount,
            direction=Transaction.OUT,
            date=now(),
            description=description or f"Transferencia a {to_account.name}",
        )

        # Ingreso
        Transaction.objects.create(
            account=to_account,
            entity=entity,
            category=category,
            amount=amount,
            direction=Transaction.IN,
            date=now(),
            description=description or f"Transferencia desde {from_account.name}",
        )
