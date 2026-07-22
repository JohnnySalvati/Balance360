import datetime
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.account import Account
    from balance360.models.import_batch import ImportBatch
    from balance360.models.transaction import Transaction
from balance360.enums import ImportRowStatus


class ImportRow(Base, TimestampMixin):
    __tablename__ = "import_rows"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    source_row: Mapped[int] = mapped_column(Integer)
    date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(String(200))
    debit: Mapped[Decimal | None] = mapped_column(Numeric)
    credit: Mapped[Decimal | None] = mapped_column(Numeric)
    status: Mapped[ImportRowStatus] = mapped_column(
        Enum(ImportRowStatus), default=ImportRowStatus.needs_review
    )
    reason: Mapped[str] = mapped_column(String(200))
    import_batch: Mapped["ImportBatch"] = relationship(back_populates="import_rows")
    account: Mapped["Account"] = relationship(back_populates="import_rows")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="import_row", passive_deletes=True
    )
