from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.category import Category
    from balance360.models.contact import Contact
    from balance360.models.currency import Currency
    from balance360.models.entity import Entity
    from balance360.models.account import Account
    from balance360.models.attachment import Attachment
    from balance360.models.import_rule import ImportRule

import uuid
import datetime
import decimal
from sqlalchemy import Uuid, Date, String, Numeric, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.models.base import Base, TimestampMixin
from balance360.enums import TransactionType

class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "date", "description", "amount", "type", name="uq_transaction"),
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
    currency_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("currencies.id")
    )
    contact_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("contacts.id")
    )
    category_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("categories.id")
    )
    is_manual: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    is_transfer: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    applied_rule_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("import_rules.id")
    )
    applied_rule: Mapped["ImportRule|None"] = relationship(
        back_populates="transactions"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="transaction"
    )
    category: Mapped["Category | None"] = relationship(
        back_populates="transactions"
    )
    contact: Mapped["Contact|None"] = relationship(
        back_populates="transactions"
    )
    currency: Mapped["Currency"] = relationship(
        back_populates="transactions"
    )
    entity: Mapped["Entity|None"] = relationship(
        back_populates="transactions"
    )
    account: Mapped["Account"] = relationship(
        back_populates="transactions"
    )

