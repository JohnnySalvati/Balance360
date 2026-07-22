import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.import_row import ImportRow
    from balance360.models.transaction import Transaction


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    import_rows: Mapped[list["ImportRow"]] = relationship(
        back_populates="import_batch", passive_deletes=True
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="import_batch", passive_deletes=True
    )
