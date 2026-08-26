import datetime
import uuid

from sqlalchemy import DateTime, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from balance360.models.base import Base, TimestampMixin


class ArcaTicket(Base, TimestampMixin):
    """Ticket de acceso de WSAA, cacheado en la base y no en un archivo.

    WSAA no emite un ticket nuevo mientras el anterior siga vigente (~12 h). Si el
    cache vive en el filesystem del contenedor, cada redeploy lo pierde y la app
    queda sin poder facturar hasta que el ticket viejo venza. En la base sobrevive
    al redeploy, y lo comparten todos los procesos que levanten contra ella.
    """

    __tablename__ = "arca_tickets"
    __table_args__ = (UniqueConstraint("env", "service", name="uq_arca_ticket_env_service"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    env: Mapped[str] = mapped_column(String(10))
    service: Mapped[str] = mapped_column(String(50))
    token: Mapped[str] = mapped_column(Text)
    sign: Mapped[str] = mapped_column(Text)
    expiration_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
