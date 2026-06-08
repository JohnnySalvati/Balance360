from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from balance360.models.transaction import Transaction
    from balance360.models.invoice import Invoice
    from balance360.models.import_rule import ImportRule    
import uuid
from sqlalchemy import Uuid, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.models.base import Base, TimestampMixin

class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_parent_id_name"),
        )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(30)
    )
    parent_id: Mapped[uuid.UUID|None] = mapped_column(
        ForeignKey("categories.id")
    )
    description: Mapped[str|None] = mapped_column(
        String(60)
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="category"
    )
    parent: Mapped[Optional["Category"]] = relationship(
        "Category", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship(
        "Category", back_populates="parent"
    )
    invoices: Mapped[list[Invoice]] = relationship(
        back_populates="category"
    )
    import_rules: Mapped[list["ImportRule"]] = relationship(
        back_populates="category"
    )


    @property
    def depth(self) -> int:
        level = 0
        node = self
        while node.parent_id:
            level += 1
            assert node.parent is not None
            node = node.parent
        return level