"""Acceso a `email_confirmations`.

La consulta importante es una sola: `get_usable_by_hash`. Que sea la única forma de resolver
un token es lo que hace que "vencido", "ya usado", "inventado" y "de un usuario que ya no
está" se colapsen en el mismo `None` — el router no puede distinguirlos ni por descuido, y esa
es exactamente la respuesta que corresponde: el remedio de los cuatro es pedir uno nuevo.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.models.email_confirmation import EmailConfirmation

# 24 horas. Alcanza para el que se registra a la noche y abre el mail al día siguiente, y no
# deja el link vivo una semana en una casilla que se puede filtrar. Vencerse es barato: el que
# llega tarde pide otro.
LIFETIME = timedelta(hours=24)


def create(db: Session, user_id: uuid.UUID, token_hash: str) -> EmailConfirmation:
    confirmation = EmailConfirmation(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + LIFETIME,
    )
    db.add(confirmation)
    db.flush()
    db.refresh(confirmation)
    return confirmation


def get_usable_by_hash(db: Session, token_hash: str) -> EmailConfirmation | None:
    """La confirmación que ese token todavía puede usar, o `None`.

    Los tres filtros van en la consulta y no en quien llama para que no exista la versión que
    se olvida de uno.
    """
    return (
        db.execute(
            select(EmailConfirmation).where(
                EmailConfirmation.token_hash == token_hash,
                EmailConfirmation.confirmed_at.is_(None),
                EmailConfirmation.expires_at > datetime.now(timezone.utc),
            )
        )
        .scalars()
        .first()
    )


def mark_confirmed(db: Session, confirmation: EmailConfirmation) -> None:
    confirmation.confirmed_at = datetime.now(timezone.utc)
    db.flush()
