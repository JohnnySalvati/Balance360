"""Cómo se ve un token de `/api` y bajo qué condiciones se emite uno.

Está separado del CRUD porque son dos cosas distintas: acá vive **cómo se ve** un token, cómo
se lo convierte en la clave con la que se lo busca y qué hace falta para que se emita; en
`crud/api_token.py`, cómo se guarda y se lee esa fila.

Las dos mitades del archivo tienen dueños distintos y conviene no confundirlos.
`generate_token` y `hash_token` no tocan la base ni conocen a ningún usuario: los usa cada
request de `/api` para resolver la credencial. `issue_for_credentials` es la puerta de
entrada —el único lugar de la app que acepta una contraseña sin sesión previa— y por eso es
la que carga con el límite de intentos, la verificación en tiempo constante y la revocación
del token anterior.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from balance360.crud import api_token as api_token_crud
from balance360.crud import user as user_crud
from balance360.exceptions import ApiTokenAuthError, TooManyAttemptsError
from balance360.models.api_token import ApiToken
from balance360.services.rate_limit import RateLimiter
from balance360.services.security import generate_opaque_token, hash_opaque_token

# El prefijo no aporta seguridad: aporta reconocimiento. Un string suelto en un `.env` o en un
# log se identifica de un vistazo, que es lo que decide si hay que rotarlo o no.
TOKEN_PREFIX = "b360_"


def generate_token() -> str:
    """Un token nuevo, en claro. **Es la única vez que existe así**: después solo queda el hash.

    El prefijo no aporta seguridad y por eso no es parte de `generate_opaque_token`: es de este
    token y de ninguno de los otros dos, que nunca salen a un `.env` ni a un log.
    """
    return TOKEN_PREFIX + generate_opaque_token()


def hash_token(token: str) -> str:
    """La clave con la que se busca la fila. El porqué del SHA-256 sin salt está en
    `services/security.py`, que es de donde salen los tres tokens opacos de la app."""
    return hash_opaque_token(token)


# Cinco intentos cada cuarto de hora, por dirección de mail. Es un presupuesto pensado para
# una persona que se equivoca al tipear —dos o tres veces, y después va a buscar la
# contraseña— y no para un cliente automático: FactuMov pide un token cuando alguien aprieta
# "conectar", o sea una vez cada varios meses.
_ISSUE_LIMITER = RateLimiter(limit=5, window_seconds=15 * 60)

# La clave es el mail y **no la IP**, que es lo que se limitaría por reflejo. Dos motivos, y
# los dos son decisivos acá:
#
# 1. Todos los pedidos legítimos vienen de la misma IP: la del servidor de FactuMov, que es
#    quien llama en nombre de cada usuario. Un límite por IP no separaría al atacante de la
#    app — los contaría juntos— y el primero que se pase deja afuera a todos los demás.
# 2. Detrás de Caddy la IP que ve la app es la del proxy salvo que se configure el reenvío, y
#    leer `X-Forwarded-For` a mano es peor que no mirar nada: cualquiera manda uno distinto
#    en cada request y el límite deja de existir.
#
# El mail no tiene esos problemas: es exactamente la cuenta que se está atacando, y cambiarlo
# para escaparse de la ventana significa atacar otra cuenta, que es justo lo que el límite
# tiene que hacer costoso. Lo que este límite **no** frena es el rociado —una contraseña
# probada contra mil direcciones distintas—; eso se frena en el borde, y por eso el módulo
# dice que es un piso y no el techo.
_INVALID_CREDENTIALS = "Mail o contraseña incorrectos."


@dataclass(frozen=True)
class IssuedToken:
    """Un token recién emitido, con lo que hace falta para contarlo.

    Lleva la fila además del texto en claro porque los dos lados son necesarios y ninguno se
    puede derivar del otro: el token solo existe acá y ya, y el `created_at` es el de la fila.
    """

    token: str
    api_token: ApiToken
    # `True` si al emitir este se revocó el anterior con el mismo nombre.
    replaced_previous: bool


def issue_for_credentials(db: Session, email: str, password: str, name: str) -> IssuedToken:
    """Cambia mail + contraseña por un token de `/api`.

    **La contraseña se usa acá y no se guarda en ningún lado.** Ese es todo el sentido del
    endpoint: el que llama la tiene un instante, la cambia por una credencial que se puede
    revocar sola, y se olvida de ella. Guardarla del otro lado sería el escenario que
    `models/api_token.py` describe como el que había que evitar —los dos sistemas convertidos
    en uno—, con el agravante de que ahora estaría escrita en una base ajena.

    **Revoca el token anterior de la misma integración.** Los tokens no caducan, así que sin
    esto cada reconexión dejaría vivo un secreto que ya no usa nadie y que nadie va a acordarse
    de apagar: N credenciales con acceso de escritura a la contabilidad, una sola en uso.
    Reemplazar es lo que el usuario cree que está haciendo cuando vuelve a conectar.
    """
    retry_after = _ISSUE_LIMITER.check(email.strip().lower())
    if retry_after is not None:
        raise TooManyAttemptsError(
            "Demasiados intentos. Probá de nuevo en un rato.", retry_after=retry_after
        )

    user = user_crud.get_by_email(db, email)
    if user is None:
        # Verificación contra un hash de mentira, que tarda lo mismo que una de verdad. Sin
        # esto, un mail que no existe contesta en microsegundos y uno que sí existe tarda lo
        # que tarda bcrypt: la diferencia se mide desde afuera y convierte el endpoint en la
        # lista de usuarios que el mensaje único trata de no ser.
        user_crud.pwd_context.dummy_verify()
        raise ApiTokenAuthError(_INVALID_CREDENTIALS)

    if not user_crud.verify_user_password(user, password):
        raise ApiTokenAuthError(_INVALID_CREDENTIALS)

    if not user.is_active:
        # Acá sí se dice qué pasa, y no es una inconsistencia con el mensaje único de arriba:
        # quien llegó hasta este punto ya demostró que la contraseña es suya, así que no queda
        # nada que ocultarle. Lo que sí haría falta es que se entere, porque "mail o
        # contraseña incorrectos" lo mandaría a cambiar una contraseña que está bien.
        raise ApiTokenAuthError("La cuenta está desactivada.")

    previous = api_token_crud.get_active_by_name(db, user.id, name)
    for old in previous:
        api_token_crud.revoke(db, old)

    token = generate_token()
    api_token = api_token_crud.create(
        db, user_id=user.id, name=name, token_hash=hash_token(token)
    )
    return IssuedToken(token=token, api_token=api_token, replaced_previous=bool(previous))
