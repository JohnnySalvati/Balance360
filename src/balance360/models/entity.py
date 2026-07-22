from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.entity_membership import EntityMembership
    from balance360.models.import_rule import ImportRule
    from balance360.models.invoice import Invoice
    from balance360.models.transaction import Transaction

import uuid

from sqlalchemy import Enum, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.enums import CondicionIva
from balance360.models.base import Base, TimestampMixin


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    condicion_iva: Mapped[CondicionIva] = mapped_column(Enum(CondicionIva))
    tax_id: Mapped[str | None] = mapped_column(String(13))
    iibb_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="0", nullable=False)
    transactions: Mapped[list[Transaction]] = relationship(back_populates="entity")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="entity")
    entity_memberships: Mapped[list["EntityMembership"]] = relationship(back_populates="entity")
    import_rules: Mapped[list["ImportRule"]] = relationship(back_populates="entity")
