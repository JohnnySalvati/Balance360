"""La prueba de que la casilla que alguien escribió al registrarse es suya.

Existe desde que el alta dejó de ser exclusivamente un trabajo de Johnny desde
Configuración → Usuarios. Cuando el que crea la cuenta es el que la va a usar, la dirección
que escribe **es** su identidad —es con lo que entra y adonde va a llegar el link para
recuperarla— y no hay ninguna razón para creerle hasta que abra un mensaje que solo puede
leer el dueño de esa casilla.

**Tabla y no dos columnas en `users`.** Reenviar el mail emite un token nuevo sin invalidar
el anterior: con columnas, cada reenvío pisaría el token del mensaje que el usuario quizás ya
tiene abierto y ese link moriría sin explicación. Y no invalidar el anterior no cuesta nada —
cada token es de un solo uso, vence solo, y los dos apuntan al mismo usuario.

**Se guarda el hash y no el token**, por lo mismo que en `api_tokens`: son 256 bits de
`secrets`, así que SHA-256 alcanza y sobra —no hay diccionario contra eso— y lo que un dump de
la base entrega deja de ser un link usable.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.user import User


class EmailConfirmation(Base, TimestampMixin):
    __tablename__ = "email_confirmations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Vencimiento absoluto y en la fila, no un cálculo sobre `created_at`: así la consulta que
    # busca el token vivo lo filtra en SQL y no existe la versión que se olvida de mirarlo.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # `None` = sin usar. Se marca en vez de borrar la fila porque "este link ya se usó" es
    # información: sin ella, un segundo click sobre el mismo mail sería indistinguible de un
    # token inventado y las dos cosas se explican distinto.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # `foreign_keys` explícito porque `TimestampMixin` ya trae `created_by` y `modified_by`
    # apuntando a `users.id`: sin esto SQLAlchemy ve tres caminos y no sabe cuál es el dueño.
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
