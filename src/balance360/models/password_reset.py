"""El permiso, con fecha de vencimiento, para elegir una contraseña nueva sin saber la vieja.

Hasta acá la única salida para una contraseña olvidada era que otro usuario entrara a
Configuración → Usuarios y la cambiara a mano — o sea que recuperar la propia cuenta dependía
de que hubiera alguien más adentro. Con un solo usuario habilitado eso no es un trámite
incómodo: es quedarse afuera de la contabilidad hasta que alguien corra un script contra la
base de producción.

Tiene la **misma forma que `api_tokens` y `email_confirmations`** —token opaco guardado como
SHA-256, vencimiento en la fila, marca de consumo en vez de borrar— y que se repita es la
decisión. Una tabla genérica de "tokens" con una columna `kind` obligaría a los tres a
compartir vencimiento, índices y reglas de limpieza, que es justo lo que no comparten.

**Vive una hora, no las 24 de la confirmación**, y no es una simetría rota: lo que está en
juego es distinto. Un token de confirmación vencido cuesta un reenvío; uno de reset vivo es la
cuenta entera para cualquiera que llegue a esa casilla. Quien lo pidió lo va a usar en el
minuto siguiente.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.user import User


class PasswordReset(Base, TimestampMixin):
    __tablename__ = "password_resets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Se llama `used_at` y no `confirmed_at` como el de al lado porque acá no se confirma
    # nada: se consume un permiso. Usar uno apaga todos los demás del mismo usuario — dos
    # links de reset vivos son dos oportunidades de cambiar la contraseña, y la segunda le
    # queda a quien pidió la primera.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
