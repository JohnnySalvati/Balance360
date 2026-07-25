from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from balance360.models.entity_membership import EntityMembership
    from balance360.models.fiscal_identity import FiscalIdentity
    from balance360.models.import_rule import ImportRule
    from balance360.models.invoice import Invoice
    from balance360.models.transaction import Transaction
from balance360.models.base import Base, TimestampMixin


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), unique=True)

    transactions: Mapped[list[Transaction]] = relationship(back_populates="entity")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="entity")
    entity_memberships: Mapped[list["EntityMembership"]] = relationship(back_populates="entity")
    import_rules: Mapped[list["ImportRule"]] = relationship(back_populates="entity")
    fiscal_identities: Mapped[list[FiscalIdentity]] = relationship(back_populates="entity")
