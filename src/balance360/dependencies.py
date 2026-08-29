from dataclasses import dataclass
from datetime import date

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from balance360.crud import api_token as api_token_crud
from balance360.crud import user as user_crud
from balance360.database import SessionLocal
from balance360.models.user import User
from balance360.services.api_token import hash_token
from balance360.services.auth import decode_access_token
from balance360.services.period import resolve_period


def get_db():
    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            raise e


def get_api_user(request: Request, db: Session = Depends(get_db)) -> User:
    """El usuario detrás de un request a `/api`: token de máquina o, si no hay, la cookie.

    Los routers de `/api` estaban montados **sin autenticación ninguna** —solo `web_router`
    llevaba `Depends(get_current_user)`—, así que cualquiera con la URL leía y escribía
    contactos, cuentas y transacciones. Eso se cierra acá, y el orden de los dos intentos es
    lo único con matiz:

    **Primero el token.** Es lo que usa FactuMov, que es el motivo por el que esta API pasa a
    estar viva. Un `Authorization` presente pero inválido **corta**: no cae a la cookie. Si
    cayera, un token revocado seguiría funcionando desde un navegador con sesión abierta, que
    es exactamente lo que revocar tiene que impedir.

    **Después la cookie**, para no romper lo que ya andaba: estos endpoints existen desde el
    desarrollo inicial y se los sigue pudiendo probar desde el navegador con la sesión puesta.
    """
    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Token invalido")
        api_token = api_token_crud.get_active_by_hash(db, hash_token(token))
        if api_token is None or not api_token.user.is_active:
            raise HTTPException(status_code=401, detail="Token invalido")
        api_token_crud.touch(db, api_token)
        return api_token.user

    return get_current_user(request, db)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Token invalido")

    try:
        user_id = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token invalido")

    user = user_crud.get_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def to_int_or_none(value, current):
    if value == "all":
        return None
    if not value:
        return current
    return int(value)


@dataclass
class Period:
    start: date
    end: date
    year: str
    month: str
    date_from: str
    date_to: str


def get_period(
    year: str = Query(default=""),
    month: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
) -> Period:

    start, end = resolve_period(
        year=to_int_or_none(year, date.today().year),
        month=to_int_or_none(month, date.today().month),
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
    )

    return Period(
        start=start, end=end, year=year, month=month, date_from=date_from, date_to=date_to
    )
