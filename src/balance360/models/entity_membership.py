import uuid 
from decimal import Decimal
from sqlalchemy import Uuid, ForeignKey, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.enums import Role
from balance360.models.base import Base, TimestampMixin
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from balance360.models.user import User
    from balance360.models.entity import Entity


class EntityMembership(Base, TimestampMixin):
    __tablename__ = "entity_memberships"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id")
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id")
    )
    role: Mapped[Role] = mapped_column(
        Enum(Role), default=Role.owner
    )
    share: Mapped[Decimal|None] = mapped_column(
        Numeric, nullable=True
    )
    user: Mapped['User'] = relationship(
        back_populates="entity_memberships",
        foreign_keys="[EntityMembership.user_id]"
    )
    entity: Mapped['Entity'] = relationship(
        back_populates="entity_memberships"
    )