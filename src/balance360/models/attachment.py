from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.invoice import Invoice
import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.models.base import Base, TimestampMixin


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(64))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    invoice: Mapped["Invoice"] = relationship(back_populates="attachments")
