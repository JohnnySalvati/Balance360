"""Acceso a `password_resets`.

Misma forma que `crud/email_confirmation.py`, con una diferencia que no es de estilo:
`invalidate_all_for_user`. Dos links de confirmación vivos son inofensivos —los dos hacen lo
mismo y lo que hacen ya está hecho—; dos links de reset vivos son dos oportunidades de cambiar
la contraseña, y la segunda le queda a quien pidió la primera.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from balance360.models.password_reset import PasswordReset

# Una hora. El que lo pidió lo va a usar en el minuto siguiente; lo que se acota es cuánto
# tiempo queda, en una casilla de mail, algo que abre la cuenta entera.
LIFETIME = timedelta(hours=1)


def create(db: Session, user_id: uuid.UUID, token_hash: str) -> PasswordReset:
    reset = PasswordReset(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + LIFETIME,
    )
    db.add(reset)
    db.flush()
    db.refresh(reset)
    return reset


def get_usable_by_hash(db: Session, token_hash: str) -> PasswordReset | None:
    return (
        db.execute(
            select(PasswordReset).where(
                PasswordReset.token_hash == token_hash,
                PasswordReset.used_at.is_(None),
                PasswordReset.expires_at > datetime.now(timezone.utc),
            )
        )
        .scalars()
        .first()
    )


def invalidate_all_for_user(db: Session, user_id: uuid.UUID) -> None:
    """Quema todos los links de reset vivos de ese usuario.

    Se llama al consumir uno. Pedir otro **no** rompe el anterior a propósito: el que no
    encuentra el primer mail pide un segundo, y dejarlo con dos links muertos sería castigarlo
    por buscar mal. Lo que no puede quedar es un permiso sin usar después de que la contraseña
    ya cambió.
    """
    db.execute(
        update(PasswordReset)
        .where(PasswordReset.user_id == user_id, PasswordReset.used_at.is_(None))
        .values(used_at=datetime.now(timezone.utc))
    )
    db.flush()
