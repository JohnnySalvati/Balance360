import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.category import Category
    from balance360.models.contact import Contact
    from balance360.models.entity import Entity
    from balance360.models.transaction import Transaction

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.enums import TransactionType
from balance360.models.base import Base, TimestampMixin


class ImportRule(Base, TimestampMixin):
    __tablename__ = "import_rules"
    __table_args__ = (
        UniqueConstraint("pattern", "transaction_type", name="uq_import_rule_pattern_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id"))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"))
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pattern: Mapped[str] = mapped_column(String(200))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="applied_rule")
    entity: Mapped["Entity|None"] = relationship(back_populates="import_rules")
    contact: Mapped["Contact|None"] = relationship(back_populates="import_rules")
    category: Mapped["Category|None"] = relationship(back_populates="import_rules")
