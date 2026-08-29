import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Uuid
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
    # **La llave de la puerta.** Un usuario inactivo no entra: lo rechaza el login y lo
    # rechaza `get_current_user` en el request siguiente, así que desactivar corta el acceso
    # de una sesión que ya estaba abierta.
    #
    # Desde que existe el registro público esto además es lo que separa "se registró" de
    # "puede ver la contabilidad": el alta propia crea la cuenta apagada y prenderla es una
    # decisión de una persona, tomada desde Configuración → Usuarios. La app **no** filtra los
    # datos por membresía en las pantallas —`entity_crud.get_all` los trae todos— así que
    # cualquiera que entre ve todo: la puerta es esto y no un scoping que no existe.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Cuándo probó que la casilla es suya, abriendo el link que le llegó. `None` en los
    # usuarios que creó Johnny a mano y en los que todavía no confirmaron: no es una condición
    # para entrar —para eso está `is_active`—, es lo que hace confiable la dirección a la que
    # se manda un reset de contraseña.
    email_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entity_memberships: Mapped[list["EntityMembership"]] = relationship(
        back_populates="user", foreign_keys="[EntityMembership.user_id]"
    )
