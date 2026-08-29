"""Generar y verificar los tokens de `/api`. La parte que no toca la base.

Está separado del CRUD porque son dos cosas distintas: acá vive **cómo se ve** un token y
cómo se lo convierte en la clave con la que se lo busca; en `crud/api_token.py`, cómo se
guarda y se lee esa fila.
"""

import hashlib
import secrets

# 32 bytes de entropía: 256 bits. Es lo que hace que buscar por hash sin salt sea seguro acá y
# no lo sea con contraseñas — no existe diccionario ni fuerza bruta contra esto.
_TOKEN_BYTES = 32

# El prefijo no aporta seguridad: aporta reconocimiento. Un string suelto en un `.env` o en un
# log se identifica de un vistazo, que es lo que decide si hay que rotarlo o no.
TOKEN_PREFIX = "b360_"


def generate_token() -> str:
    """Un token nuevo, en claro. **Es la única vez que existe así**: después solo queda el hash."""
    return TOKEN_PREFIX + secrets.token_urlsafe(_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """La clave con la que se busca la fila.

    Determinístico y sin salt a propósito. Un hash con salt obligaría a traer todos los tokens
    y probarlos de a uno en cada request; con SHA-256 la búsqueda es un índice único. Lo que
    haría insegura esa decisión —que el original sea adivinable— no aplica: el original lo
    genera `generate_token`, no una persona.
    """
    return hashlib.sha256(token.encode()).hexdigest()
