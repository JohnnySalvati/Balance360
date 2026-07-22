import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.entity_membership import EntityMembership


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(50), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(72))
    full_name: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    entity_memberships: Mapped[list["EntityMembership"]] = relationship(
        back_populates="user", foreign_keys="[EntityMembership.user_id]"
    )
