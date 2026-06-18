from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.transaction import Transaction
import uuid
from sqlalchemy import Uuid, ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.models.base import Base, TimestampMixin

class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id")
    )
    filename: Mapped[str] = mapped_column(
        String(255)
    )
    stored_filename: Mapped[str] = mapped_column(
        String(64)
    )
    mime_type: Mapped[str|None] = mapped_column(
        String(100)
    )
    file_size: Mapped[int] = mapped_column(
        Integer
    )
    transaction: Mapped[Transaction] = relationship(
        back_populates="attachments"
    )