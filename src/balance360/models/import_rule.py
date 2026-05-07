import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Uuid, ForeignKey, String, Integer
from balance360.models.base import Base, TimestampMixin

class ImportRule(Base, TimestampMixin):
    __tablename__ = "import_rules"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("entities.id")
    )
    contact_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("contacts.id")
    )
    category_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("categories.id")
    )
    pattern: Mapped[str] = mapped_column(
        String(200), unique=True
    )
    applied: Mapped[int] = mapped_column(
        Integer, default=0
    )