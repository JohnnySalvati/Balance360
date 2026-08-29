from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from balance360.models.entity_membership import EntityMembership
    from balance360.models.fiscal_identity import FiscalIdentity
    from balance360.models.import_rule import ImportRule
    from balance360.models.invoice import Invoice
    from balance360.models.transaction import Transaction
from balance360.models.base import Base, TimestampMixin


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), unique=True)

    # Identidad visible en los mails que manda esta entidad. El transporte SMTP es
    # uno solo para toda la app (una casilla autenticada, que es lo que sostiene SPF
    # y DKIM); lo unico que cambia por entidad es como se presenta. Por eso la
    # direccion propia va en Reply-To y no en From: un From ajeno no valida y los
    # servidores lo marcan como spam o lo reescriben.
    email_display_name: Mapped[str | None] = mapped_column(String(100))
    email_reply_to: Mapped[str | None] = mapped_column(String(150))
    email_signature: Mapped[str | None] = mapped_column(Text)

    transactions: Mapped[list[Transaction]] = relationship(back_populates="entity")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="entity")
    entity_memberships: Mapped[list["EntityMembership"]] = relationship(back_populates="entity")
    import_rules: Mapped[list["ImportRule"]] = relationship(back_populates="entity")
    fiscal_identities: Mapped[list["FiscalIdentity"]] = relationship(
        secondary="entity_fiscal_identities", back_populates="entities"
    )

    @property
    def fiscal_identity_ids(self) -> list[uuid.UUID]:
        """Los ids de las identidades fiscales, que es como las nombran los schemas.

        `EntityCreate` y `EntityUpdate` reciben ids, asi que `EntityRead` devuelve ids: entrada
        y salida hablan el mismo idioma y el cliente puede mandar de vuelta lo que recibio. Sin
        esta propiedad la relacion se llama `fiscal_identities` y el campo `fiscal_identity_ids`
        no existe en ningun lado, con lo cual `from_attributes` no lo encuentra y **la respuesta**
        no valida: un 500 en cada GET de `/api/entities`, que es por donde FactuMov prueba el
        token.
        """
        return [identity.id for identity in self.fiscal_identities]
