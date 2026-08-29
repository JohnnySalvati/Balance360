"""Recuperar la propia contraseña sin depender de que haya otro usuario adentro.

Hasta acá la única salida era que alguien más entrara a Configuración → Usuarios y la cambiara
a mano. Con un solo usuario habilitado eso no es un trámite incómodo: es quedarse afuera de la
contabilidad hasta que alguien corra un script contra la base de producción. Pasó de verdad.

Las dos mitades del flujo tienen cuidados distintos y conviene no mezclarlos:

- **Pedirlo** no puede contar si esa dirección tiene cuenta. Contesta lo mismo siempre y manda
  un mail en las dos ramas — también en la que no encontró a nadie, y eso no es una cortesía:
  si esa rama no mandara nada, sería la única que no puede fallar por un problema de SMTP, y el
  error pasaría a significar "esa dirección existe".
- **Usarlo** no tiene nada que ocultar: el token sirve o no sirve, y las cuatro formas de no
  servir —inventado, vencido, ya usado, de un usuario borrado— tienen el mismo remedio.
"""

import logging

from sqlalchemy.orm import Session

from balance360.crud import password_reset as reset_crud
from balance360.crud import user as user_crud
from balance360.exceptions import TooManyAttemptsError
from balance360.models.user import User
from balance360.services import notifications
from balance360.services.rate_limit import RateLimiter
from balance360.services.security import generate_opaque_token, hash_opaque_token

logger = logging.getLogger(__name__)

# Cinco pedidos cada cuarto de hora por dirección, igual que el registro y que `/api/tokens`.
# Lo que acota no es un ataque de contraseñas —acá no se prueba ninguna— sino que el formulario
# sea una forma gratis de llenarle la casilla a otro.
_REQUEST_LIMITER = RateLimiter(limit=5, window_seconds=15 * 60)


def request(db: Session, email: str) -> None:
    """Manda el link para elegir una contraseña nueva. **No dice si la dirección existe.**

    El commit va antes del mail, igual que en el registro: primero se guarda el token que el
    link promete, después sale el link. Al revés, una transacción que aborte deja al usuario
    con un link que no va a funcionar nunca.
    """
    normalized = email.strip().lower()

    retry_after = _REQUEST_LIMITER.check(normalized)
    if retry_after is not None:
        raise TooManyAttemptsError(
            "Demasiados intentos. Probá de nuevo en un rato.", retry_after=retry_after
        )

    user = user_crud.get_by_email(db, normalized)
    if user is None:
        notifications.send_password_reset_unknown(normalized)
        return

    token = generate_opaque_token()
    reset_crud.create(db, user.id, hash_opaque_token(token))
    db.commit()
    notifications.send_password_reset(user.email, user.full_name, token)


def get_user_for_token(db: Session, token: str) -> User | None:
    """Quién es el dueño de ese link, o `None` si el link no sirve.

    Existe aparte de `consume` para que la pantalla pueda decir "este link ya no sirve" **antes**
    de que la persona escriba una contraseña dos veces. No consume nada: abrir el mail no puede
    quemar el permiso.
    """
    reset = reset_crud.get_usable_by_hash(db, hash_opaque_token(token))
    return reset.user if reset is not None else None


def consume(db: Session, token: str, new_password: str) -> User | None:
    """Cambia la contraseña y apaga el permiso. `None` si el token ya no servía.

    **Usar el link confirma la dirección.** Haberlo abierto prueba lo mismo que prueba el link
    de confirmación: que quien lo abrió tiene la casilla. Sin esto, alguien que se registró,
    se equivocó de contraseña y recuperó por acá seguiría figurando como no confirmado para
    siempre.

    **Usarlo apaga todos los demás.** Dos links de reset vivos son dos oportunidades de cambiar
    la contraseña, y la segunda le queda a quien pidió la primera.

    **No abre sesión**: el token vivió en una casilla de mail, y convertirlo en cookie dejaría
    adentro a cualquiera con acceso a ese mensaje. Después de cambiarla se entra por el login,
    que es una pantalla de distancia.

    Lo que **no** puede hacer —y hay que saberlo— es cerrar las sesiones abiertas: las de esta
    app son un JWT firmado con vencimiento propio, sin fila que revocar, así que una sesión
    ajena que ya estaba abierta sigue viva hasta ocho horas. Está anotado en `PENDING.md`.
    """
    reset = reset_crud.get_usable_by_hash(db, hash_opaque_token(token))
    if reset is None:
        return None

    user = reset.user
    user_crud.set_password(db, user, new_password)
    user_crud.mark_email_confirmed(db, user)
    reset_crud.invalidate_all_for_user(db, user.id)
    db.commit()

    notifications.send_password_changed(user.email, user.full_name)
    logger.info("%s cambió su contraseña con un link de recuperación.", user.email)
    return user
