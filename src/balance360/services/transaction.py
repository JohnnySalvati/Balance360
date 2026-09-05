"""Reglas del borrado de una transacción.

La única por ahora: si la transacción es el pago de un comprobante, borrarla tiene
que deshacer el pago. `register_payment` (services/invoice.py) es lo único que ata
una transacción a un comprobante —le pone `invoice_id` y marca `invoice.paid`—, así
que `transaction.invoice` presente ⇒ esta transacción es ese pago y no otra cosa.

Sin esto el comprobante quedaba `paid=True` sin ninguna transacción que lo
respalde: no reaparecía el botón "Registrar pago" en el detalle y el cobro seguía
sumando en los reportes aunque su asiento ya no existiera.
"""

from sqlalchemy.orm import Session

from balance360.crud import transaction as transaction_crud
from balance360.models.transaction import Transaction


def delete(db: Session, transaction: Transaction) -> None:
    if transaction.invoice is not None:
        transaction.invoice.paid = False
    transaction_crud.delete(db, transaction)
