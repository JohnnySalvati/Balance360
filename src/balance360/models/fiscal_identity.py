from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from balance360.models.entity import Entity
    from balance360.models.invoice import Invoice
from balance360.enums import CondicionIva
from balance360.models.base import Base, TimestampMixin


class FiscalIdentity(Base, TimestampMixin):
    __tablename__ = "fiscal_identities"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"))
    name: Mapped[str] = mapped_column(String(150), unique=True)
    condicion_iva: Mapped[CondicionIva] = mapped_column(Enum(CondicionIva))
    tax_id: Mapped[str] = mapped_column(String(11), unique=True)
    iibb_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="0", nullable=False)
    address: Mapped[str | None] = mapped_column(String(200))
    iibb: Mapped[str | None] = mapped_column(String(50))
    start_date: Mapped[date | None] = mapped_column(Date)

    entity: Mapped[Entity] = relationship(back_populates="fiscal_identities")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="fiscal_identity")
