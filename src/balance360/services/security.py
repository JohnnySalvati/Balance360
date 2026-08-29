"""Los tokens opacos de la app: cómo se generan y con qué clave se buscan.

Un token opaco es un secreto sin estructura —no dice nada de quién es ni de para qué sirve—
que solo vale porque hay una fila que lo reconoce. Los usan las tres credenciales que no son
una contraseña: el token de `/api`, el link de confirmación de mail y el de reset.

**Se guardan hasheados con SHA-256, no con el hash lento de las contraseñas.** Una contraseña
la elige una persona y hay que encarecerle cada intento a quien se lleve la tabla; esto son 32
bytes de `secrets`, o sea 256 bits que ningún diccionario adivina. Un hash lento acá solo
agregaría latencia a cada request a cambio de nada.

Y sin salt, a propósito: con salt habría que traer todas las filas y probarlas de a una en
cada request, mientras que SHA-256 determinístico convierte la búsqueda en un índice único. Lo
que haría insegura esa decisión —que el original sea adivinable— no aplica cuando el original
lo genera `secrets` y no una persona.
"""

import hashlib
import secrets

# 32 bytes = 256 bits. Es lo que hace que buscar por hash sin salt sea seguro acá.
_TOKEN_BYTES = 32


def generate_opaque_token() -> str:
    """Un secreto nuevo, en claro. **Es la única vez que existe así**: después solo queda el
    hash, y si se pierde el texto lo que corresponde es emitir otro, no recuperar este."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_opaque_token(token: str) -> str:
    """La clave con la que se busca la fila."""
    return hashlib.sha256(token.encode()).hexdigest()


# El mínimo de largo de una contraseña, en el único lugar donde vive.
#
# Sin reglas de composición —una mayúscula, un número, un símbolo—: empujan a `Password1!` y
# NIST las desaconseja desde 2017. El largo es lo que importa y es lo único que se pide.
#
# Ocho porque es lo que ya exigía el reset de Configuración → Usuarios: subirlo acá dejaría dos
# reglas distintas para la misma contraseña según por qué pantalla se cambie.
PASSWORD_MIN_LENGTH = 8
