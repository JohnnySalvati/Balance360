from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.transaction import Transaction
    from balance360.models.invoice import Invoice
    from balance360.models.entity_membership import EntityMembership

import uuid 
from sqlalchemy import Uuid, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.enums import CondicionIva
from balance360.models.base import Base, TimestampMixin

class Entity(Base, TimestampMixin):
    __tablename__ = "entities"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(30), unique=True
    )
    condicion_iva: Mapped[CondicionIva] = mapped_column(
        Enum(CondicionIva)
    )
    tax_id: Mapped[str|None] = mapped_column(
        String(13)
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="entity"
    )
    invoices: Mapped[list['Invoice']] = relationship(
        back_populates="entity"
    )
    entity_memberships: Mapped[list['EntityMembership']] = relationship(
        back_populates="entity"
    )
