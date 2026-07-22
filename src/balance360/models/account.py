from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.currency import Currency
    from balance360.models.import_row import ImportRow
    from balance360.models.transaction import Transaction
import uuid

import sqlalchemy
from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.enums import AccountType
from balance360.models.base import Base, TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(30))
    type: Mapped[AccountType] = mapped_column(
        sqlalchemy.Enum(AccountType), default=AccountType.bank
    )
    currency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("currencies.id"))
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")
    currency: Mapped["Currency"] = relationship(back_populates="accounts")
    import_rows: Mapped[list["ImportRow"]] = relationship(back_populates="account")
