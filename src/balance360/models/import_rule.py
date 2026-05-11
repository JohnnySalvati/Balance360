import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.transaction import Transaction

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid, ForeignKey, String, Enum, Boolean
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
        String(200), unique=True
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="applied_rule"
    )
