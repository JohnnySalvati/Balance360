from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.category import Category
    from balance360.models.contact import Contact
    from balance360.models.currency import Currency
    from balance360.models.entity import Entity
    from balance360.models.account import Account
    from balance360.models.attachment import Attachment

import uuid
import datetime
import decimal
from sqlalchemy import Uuid, Date, String, Numeric, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.models.base import Base, TimestampMixin
from balance360.enums import TransactionType

class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
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
    from_account_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("accounts.id")
    )
    to_account_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("accounts.id")
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
    to_account: Mapped["Account|None"] = relationship(
        back_populates="transactions_to",
        foreign_keys=[to_account_id]
    )
    from_account: Mapped["Account|None"] = relationship(
        back_populates="transactions_from",
        foreign_keys=[from_account_id]
    )