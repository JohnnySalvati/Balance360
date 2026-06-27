from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.currency import Currency

import uuid
import datetime
from decimal import Decimal
from sqlalchemy import Uuid, ForeignKey, Date, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.models.base import Base, TimestampMixin


class ExchangeRate(Base, TimestampMixin):
    __tablename__ = "exchange_rates"
    __table_args__ = (UniqueConstraint("currency_id", "date", name="uq_exchange_rate"),)

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
    currency: Mapped["Currency"] = relationship(
        back_populates="exchange_rates"
    )