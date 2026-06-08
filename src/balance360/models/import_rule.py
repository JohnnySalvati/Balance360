import uuid
from typing import TYPE_CHECKING
from decimal import Decimal

if TYPE_CHECKING:
    from balance360.models.transaction import Transaction
    from balance360.models.entity import Entity
    from balance360.models.contact import Contact
    from balance360.models.category import Category

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid, ForeignKey, String, Enum, Boolean, UniqueConstraint, Numeric
from balance360.models.base import Base, TimestampMixin
from balance360.enums import TransactionType
class ImportRule(Base, TimestampMixin):
    __tablename__ = "import_rules"
    
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("entities.id")
    )
    contact_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("contacts.id")
    )
    category_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("categories.id")
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType), nullable=False
    )
    is_transfer: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    pattern: Mapped[str] = mapped_column(
        String(200)
    )
    min_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2)
    )
    max_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2)
    )
    
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="applied_rule"
    )
    entity: Mapped["Entity|None"] = relationship(
        back_populates="import_rules"
    )
    contact: Mapped["Contact|None"] = relationship(
        back_populates="import_rules"
    )
    category: Mapped["Category|None"] = relationship(
        back_populates="import_rules"
    )