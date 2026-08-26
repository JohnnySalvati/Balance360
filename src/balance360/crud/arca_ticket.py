import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.models.arca_ticket import ArcaTicket


def get(db: Session, env: str, service: str) -> ArcaTicket | None:
    stmt = select(ArcaTicket).where(ArcaTicket.env == env).where(ArcaTicket.service == service)
    return db.execute(stmt).scalars().first()


def save(
    db: Session,
    env: str,
    service: str,
    token: str,
    sign: str,
    expiration_time: datetime.datetime,
) -> ArcaTicket:
    """Guarda el ticket del par (env, service), pisando el anterior si lo hay.

    Es un upsert y no un insert porque de cada par existe una fila sola: el ticket
    viejo no sirve para nada una vez que WSAA emitio el nuevo.
    """
    ticket = get(db, env, service)

    if not ticket:
        ticket = ArcaTicket(env=env, service=service)
        db.add(ticket)

    ticket.token = token
    ticket.sign = sign
    ticket.expiration_time = expiration_time
    db.flush()
    return ticket
