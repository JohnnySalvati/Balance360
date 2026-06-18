from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.category import Category
    from balance360.models.contact import Contact
    from balance360.models.entity import Entity
    from balance360.models.account import Account
    from balance360.models.attachment import Attachment
    from balance360.models.import_rule import ImportRule
    from balance360.models.invoice import Invoice

import uuid
import datetime
import decimal
from sqlalchemy import Uuid, Date, String, Numeric, Enum, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.models.base import Base, TimestampMixin
from balance360.enums import TransactionType, ClassificationStatus

class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("source_file", "source_row", "type", name="uq_transaction"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    date: Mapped[datetime.date] = mapped_column(
        Date
    )
    description: Mapped[str] = mapped_column(
        String(200)
    )
    amount: Mapped[decimal.Decimal] = mapped_column(
        Numeric(precision=18, scale=2)
    )
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType)
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id"), nullable=False
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
    invoice_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("invoices.id")
    )
    is_manual: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    is_transfer: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    applied_rule_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("import_rules.id", ondelete="SET NULL")
    )
    source_file: Mapped[str|None] = mapped_column(
        String
    )
    source_row: Mapped[int|None] = mapped_column(
        Integer
    )
    applied_rule: Mapped["ImportRule|None"] = relationship(
        back_populates="transactions"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="transaction"
    )
    invoice: Mapped["Invoice|None"] = relationship(
        back_populates="transaction"
    )
    category: Mapped["Category | None"] = relationship(
        back_populates="transactions"
    )
    contact: Mapped["Contact|None"] = relationship(
        back_populates="transactions"
    )
    entity: Mapped["Entity|None"] = relationship(
        back_populates="transactions"
    )
    account: Mapped["Account"] = relationship(
        back_populates="transactions"
    )


    @property
    def classification_status(self) -> ClassificationStatus:
        match (self.is_manual, self.applied_rule is None):
            case (False, True):
                return ClassificationStatus.unclassified
            case (False, False):
                return ClassificationStatus.auto_classified
            case (True, True):
                return ClassificationStatus.manual_no_rule
            case (True, False):
                return ClassificationStatus.manual_with_rule
