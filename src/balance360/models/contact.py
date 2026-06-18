from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance360.models.transaction import Transaction
    from balance360.models.invoice import Invoice
    from balance360.models.import_rule import ImportRule
import uuid
from sqlalchemy import Uuid, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from balance360.models.base import Base, TimestampMixin
from balance360.enums import ContactType, CondicionIva, DocType

class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(60)
    )
    condicion_iva: Mapped[CondicionIva] = mapped_column(
        Enum(CondicionIva)
    )
    doc_type: Mapped[DocType] = mapped_column(
        Enum(DocType)
    )
    tax_id: Mapped[str|None] = mapped_column(
        String(13)
    )
    contact_type: Mapped[ContactType] = mapped_column(
        Enum(ContactType)
    )
    email: Mapped[str|None] = mapped_column(
        String(254)
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="contact"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="contact"
    )
    import_rules: Mapped[list["ImportRule"]] = relationship(
        back_populates="contact"
    )
