"""El alta propia: alguien crea su cuenta y confirma su dirección, sin que nadie la cree por él.

Hasta acá los usuarios los creaba Johnny desde Configuración → Usuarios. Eso sigue existiendo
y sigue siendo el camino normal; esto es la puerta de calle.

**La cuenta nace apagada (`is_active=False`) y esa es la decisión que sostiene todo lo demás.**
Las pantallas de Balance360 no filtran por membresía —`entity_crud.get_all` trae todas las
entidades, y cualquiera adentro ve la contabilidad entera y puede administrar usuarios—, así
que "registrarse" no puede significar "entrar". Significa anotarse: la cuenta existe, prueba
que la casilla es suya, y queda esperando que una persona la habilite. Prender el interruptor
es un click en Configuración → Usuarios, y ahí sale el mail de "ya podés entrar".

La alternativa —dejar entrar y limitar lo que ve— es un sistema de permisos por entidad que
esta app no tiene. Escribirlo para poder abrir el registro sería empezar por el final.

**Registrarse contesta siempre lo mismo**, exista o no la dirección: es la misma regla que el
login y `/api/tokens`, y por el mismo motivo. Un "ese mail ya está registrado" convierte al
formulario en la lista de quién tiene cuenta acá.
"""

import logging

from sqlalchemy.orm import Session

from balance360.crud import email_confirmation as confirmation_crud
from balance360.crud import user as user_crud
from balance360.exceptions import TooManyAttemptsError
from balance360.models.user import User
from balance360.services import notifications
from balance360.services.rate_limit import RateLimiter
from balance360.services.security import generate_opaque_token, hash_opaque_token

logger = logging.getLogger(__name__)

# Cinco altas cada cuarto de hora por dirección. Es el mismo presupuesto que `/api/tokens` y
# alcanza de sobra para el que se equivocó tipeando; lo que acota es que este formulario
# —que manda un mail y escribe una fila— sea gratis de repetir mil veces.
_REGISTER_LIMITER = RateLimiter(limit=5, window_seconds=15 * 60)

# Los dos límites de la tabla `users`, que son cortos y hay que decirlos antes de que la base
# los rechace con un error que no explica nada.
EMAIL_MAX_LENGTH = 50
FULL_NAME_MAX_LENGTH = 30


def register(db: Session, email: str, password: str, full_name: str) -> None:
    """Crea la cuenta —apagada— y manda el link de confirmación.

    **No devuelve nada y no distingue los casos hacia afuera.** Adentro hay tres ramas y las
    tres terminan mandando un mail, que es lo que hace que las tres tarden parecido y puedan
    fallar igual:

    1. Dirección nueva: se crea el usuario y sale el link.
    2. Dirección registrada y sin confirmar: sale un link nuevo y **no se toca la contraseña**.
       Pisarla sería una toma de cuenta completa — al atacante le alcanzaría con registrarse
       encima de una cuenta pendiente y esperar a que el dueño, que justamente está esperando
       un mail, abra el link que le llegue.
    3. Dirección ya confirmada: le llega un aviso de que la cuenta existe. Ese mail es lo único
       que puede contar qué pasó, y llega a la casilla del dueño, que es quien tiene derecho a
       saberlo.

    **El hash de la contraseña se calcula siempre**, aunque en dos de las tres ramas se tire.
    Es lo más caro del camino: hashear solo al crear haría que una dirección ya registrada
    conteste notoriamente más rápido, y la respuesta idéntica no serviría de nada.
    """
    normalized = email.strip().lower()

    retry_after = _REGISTER_LIMITER.check(normalized)
    if retry_after is not None:
        raise TooManyAttemptsError(
            "Demasiados intentos. Probá de nuevo en un rato.", retry_after=retry_after
        )

    hashed = user_crud.hash_password(password)
    existing = user_crud.get_by_email(db, normalized)

    if existing is None:
        user = user_crud.create_with_hash(
            db,
            email=normalized,
            hashed_password=hashed,
            full_name=full_name.strip(),
            # Apagada. Es la única línea de este archivo que hay que leer dos veces.
            is_active=False,
        )
        _send_confirmation(db, user)
        notifications.notify_operator_registration(user.email, user.full_name)
        return

    if existing.email_confirmed_at is None:
        _send_confirmation(db, existing)
        return

    notifications.send_account_exists(existing.email, existing.full_name)


def _send_confirmation(db: Session, user: User) -> None:
    """Emite un token de confirmación y manda el link.

    **El commit va antes del mail.** Sin eso, la transacción queda abierta durante toda la
    conexión SMTP —que puede tardar hasta el timeout— y, sobre todo, el link podría salir
    nombrando un token que una transacción abortada nunca llegue a escribir. Primero se guarda
    lo que el link promete, después se manda el link.
    """
    token = generate_opaque_token()
    confirmation_crud.create(db, user.id, hash_opaque_token(token))
    db.commit()
    notifications.send_confirmation(user.email, user.full_name, token)


def confirm(db: Session, token: str) -> User | None:
    """Consume el link y marca la dirección como probada. `None` si el token no sirve.

    Token inventado, vencido, ya usado y de un usuario borrado dan el mismo `None`: el CRUD ya
    los colapsa, así que esto no puede distinguirlos ni por descuido. Es la respuesta correcta
    —el remedio de los cuatro es pedir uno nuevo— y no hay nada que enumerar: son 256 bits.

    **Confirmar no abre sesión.** Sería mejor UX, pero el token vivió 24 horas en una casilla:
    convertirlo en cookie dejaría adentro a cualquiera con acceso a ese mensaje. Y acá ni
    siquiera alcanzaría — la cuenta todavía está apagada.
    """
    confirmation = confirmation_crud.get_usable_by_hash(db, hash_opaque_token(token))
    if confirmation is None:
        return None

    confirmation_crud.mark_confirmed(db, confirmation)
    user = user_crud.mark_email_confirmed(db, confirmation.user)
    logger.info("%s confirmó su dirección.", user.email)
    return user
