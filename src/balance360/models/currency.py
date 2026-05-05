from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.transaction import Transaction

import uuid
import datetime
from decimal import Decimal
from sqlalchemy import Uuid, String, Boolean, ForeignKey, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.models.base import Base, TimestampMixin

class Currency(Base, TimestampMixin):
    __tablename__ = "currencies"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(
         String(5), unique=True
    )
    name: Mapped[str] = mapped_column(
        String(50)
    )
    is_bond: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    transactions: Mapped[list["Transaction"]] = relationship(
            back_populates="currency"
    )

class ExchangeRate(Base, TimestampMixin):
    __tablename__ = "exchange_rates"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    currency_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("currencies.id")
    )
    date: Mapped[datetime.date] = mapped_column(
        Date
    )
    rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6)
    )
    