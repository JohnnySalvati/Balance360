import uuid
from decimal import Decimal

from pydantic import BaseModel

from balance360.enums import Role


class EntityMembershipCreate(BaseModel):
    user_id: uuid.UUID
    entity_id: uuid.UUID
    role: Role
    share: Decimal | None


class EntityMembershipUpdate(BaseModel):
    role: Role | None
    share: Decimal | None
