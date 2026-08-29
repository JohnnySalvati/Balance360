import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.models.api_token import ApiToken


def get_active_by_hash(db: Session, token_hash: str) -> ApiToken | None:
    """El token vivo con ese hash, o `None`.

    Filtra `revoked_at` acá y no en quien llama para que no exista la versión de esta consulta
    que se olvida de mirarlo: revocar tiene que cortar el acceso en el request siguiente.
    """
    return (
        db.execute(
            select(ApiToken).where(
                ApiToken.token_hash == token_hash,
                ApiToken.revoked_at.is_(None),
            )
        )
        .scalars()
        .first()
    )


def get_all_for_user(db: Session, user_id: uuid.UUID) -> list[ApiToken]:
    tokens = (
        db.execute(
            select(ApiToken)
            .where(ApiToken.user_id == user_id)
            .order_by(ApiToken.created_at.desc())
        )
        .scalars()
        .all()
    )
    return list(tokens)


def create(db: Session, user_id: uuid.UUID, name: str, token_hash: str) -> ApiToken:
    api_token = ApiToken(user_id=user_id, name=name, token_hash=token_hash)
    db.add(api_token)
    db.flush()
    db.refresh(api_token)
    return api_token


def touch(db: Session, api_token: ApiToken) -> None:
    """Deja constancia de que este token se usó recién.

    Sin `flush`: lo escribe el commit que hace `get_db` al final del request. Forzarlo acá
    abriría la escritura antes de saber si el request va a terminar bien, y lo que se está
    anotando —"alguien entró con esta credencial"— no cambia por eso.
    """
    api_token.last_used_at = datetime.now(timezone.utc)


def revoke(db: Session, api_token: ApiToken) -> None:
    api_token.revoked_at = datetime.now(timezone.utc)
    db.flush()
