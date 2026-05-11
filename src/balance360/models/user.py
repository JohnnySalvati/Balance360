import uuid
from sqlalchemy import Uuid, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from balance360.models.base import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(50), unique=True
    )
    hashed_password: Mapped[str] = mapped_column(
        String(60)
    )
    full_name: Mapped[str] = mapped_column(
        String(30)
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )

    