from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.account import Account
    from balance360.models.exchange_rate import ExchangeRate

import uuid
from sqlalchemy import Uuid, String, Boolean
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
    accounts: Mapped[list["Account"]] = relationship(
        back_populates="currency"
    )
    exchange_rates: Mapped[list["ExchangeRate"]] = relationship(
        back_populates="currency"
    )
