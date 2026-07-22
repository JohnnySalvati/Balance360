from dataclasses import dataclass
from datetime import date

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from balance360.crud import user as user_crud
from balance360.database import SessionLocal
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


def get_current_user(request: Request, db: Session = Depends(get_db)):
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
