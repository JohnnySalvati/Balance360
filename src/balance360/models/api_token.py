"""Una credencial de máquina: deja entrar a `/api` a algo que no es una persona.

Existe por FactuMov, que emite comprobantes y necesita registrarlos acá. No podía entrar con
lo que ya había: `get_current_user` resuelve la cookie que el navegador recibe después de un
login con contraseña, y del otro lado no hay navegador ni hay nadie tipeando. La alternativa
—que FactuMov guarde la contraseña de Johnny y haga login como él— convierte a los dos
sistemas en uno solo: cualquiera que lea esa variable de entorno entra a Balance360 con todos
los permisos y sin dejar rastro de que fue la otra app.

Un token separado arregla las tres cosas de una: se revoca sin tocar la contraseña, se sabe
quién entró (`last_used_at`, y el nombre lo dice), y lo que se filtra si se filtra es el
acceso de una app, no la identidad de una persona.

**Se guarda el hash y no el token**, igual que las contraseñas. Pero con SHA-256 y no con el
hash lento que usan ellas, y eso es a propósito: una contraseña la elige una persona y hay que
encarecerle el intento a quien se lleve la tabla, mientras que esto son 32 bytes de
`secrets.token_urlsafe` — no hay diccionario que lo adivine, y un hash lento solo agregaría
latencia a cada request de la integración a cambio de nada.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.user import User


class ApiToken(Base, TimestampMixin):
    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # El token actúa **como** este usuario: hereda sus entidades y sus permisos, y no los
    # amplía. Es lo que hace que la autorizacion por membresia siga valiendo del otro lado de
    # la API sin escribir un segundo sistema de permisos.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # Para qué es. Sale en el listado y es lo único que permite revocar el correcto cuando hay
    # más de uno ("FactuMov", "FactuMov pruebas").
    name: Mapped[str] = mapped_column(String(50))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Cuándo se usó por última vez. Es la respuesta a "¿esto todavía lo usa alguien?", que es
    # la pregunta previa a revocar cualquier credencial vieja.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # `None` = vivo. Timestamp y no booleano, como el resto del proyecto: revocar es un hecho
    # con fecha, y esa fecha es lo primero que se busca cuando algo dejó de andar.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # `foreign_keys` explícito porque `TimestampMixin` ya trae `created_by` y `modified_by`
    # apuntando a `users.id`: sin esto SQLAlchemy ve tres caminos y no sabe cuál es el dueño.
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
