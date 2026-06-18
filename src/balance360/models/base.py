import uuid
from datetime import datetime
from sqlalchemy import  DateTime, ForeignKey, func, Uuid
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
class Base(DeclarativeBase):
    pass
class TimestampMixin():
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
        )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
        )
    created_by: Mapped[uuid.UUID|None] = mapped_column(
        Uuid, ForeignKey("users.id")
    )
    modified_by: Mapped[uuid.UUID|None] = mapped_column(
        Uuid, ForeignKey("users.id")
    )