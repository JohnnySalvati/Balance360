"""Lista y revoca los tokens de `/api` de un usuario. Se corre a mano, del lado del servidor.

    uv run python revoke_api_token.py miguelsalvati@gmail.com             # los lista
    uv run python revoke_api_token.py miguelsalvati@gmail.com FactuMov    # revoca ese

Es el complemento de `create_api_token.py`: emitir sin poder revocar deja una credencial que
solo se puede apagar con un UPDATE a mano contra la base de producción, que es justo lo que no
hay que estar haciendo el día que un token se filtra.

**Lista antes de revocar, y por eso el nombre es opcional.** Sin el segundo argumento no toca
nada: imprime los tokens con su `last_used_at`, que es la pregunta previa a revocar cualquier
credencial vieja —"¿esto todavía lo usa alguien?"—. Un script que solo revocara obligaría a
adivinar cuál de dos tokens con nombre parecido es el que está en uso.

Sigue siendo un script y no una pantalla por lo mismo que el otro: se usa una vez cada mucho,
del lado del servidor, por quien ya tiene acceso a la base.
"""

import sys
from datetime import datetime

from balance360.crud import api_token as api_token_crud
from balance360.crud import user as user_crud
from balance360.database import SessionLocal
from balance360.models.api_token import ApiToken

# Cuántos caracteres del UUID se muestran. Ocho alcanzan para desempatar dos tokens del mismo
# nombre a ojo, y el prefijo se acepta como identificador al revocar: pegar el UUID entero
# desde una terminal remota es exactamente el paso donde se cuela un error de copiado.
_ID_CHARS = 8


def _fmt(moment: datetime | None) -> str:
    """La fecha como se lee, o `nunca`. En UTC, que es como está guardada: convertir a hora
    local acá haría que la fecha del script y la de la base no coincidan al compararlas."""
    return moment.strftime("%Y-%m-%d %H:%M") if moment is not None else "nunca"


def _print_tokens(tokens: list[ApiToken]) -> None:
    rows = [
        (
            str(token.id)[:_ID_CHARS],
            token.name,
            _fmt(token.created_at),
            _fmt(token.last_used_at),
            "vivo" if token.revoked_at is None else f"revocado {_fmt(token.revoked_at)}",
        )
        for token in tokens
    ]
    headers = ("id", "nombre", "creado", "ultimo uso", "estado")
    widths = [max(len(row[i]) for row in (*rows, headers)) for i in range(len(headers))]

    print("  ".join(header.ljust(width) for header, width in zip(headers, widths)).rstrip())
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())


def _match(tokens: list[ApiToken], needle: str) -> list[ApiToken]:
    """Los tokens **vivos** que ese texto identifica: por nombre exacto o por prefijo del id.

    Los revocados quedan afuera a propósito. Revocar dos veces no rompe nada, pero un
    "revocado" impreso sobre algo que ya estaba apagado desde marzo es una respuesta que
    tranquiliza sin motivo: el token que estabas buscando podría seguir vivo con otro nombre.
    """
    alive = [token for token in tokens if token.revoked_at is None]
    return [token for token in alive if token.name == needle or str(token.id).startswith(needle)]


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2

    email = sys.argv[1]
    needle = sys.argv[2] if len(sys.argv) == 3 else None

    with SessionLocal() as db:
        user = user_crud.get_by_email(db, email)
        if user is None:
            print(f"No hay ningún usuario con el mail {email}.")
            return 1

        tokens = api_token_crud.get_all_for_user(db, user.id)
        if not tokens:
            print(f"{email} no tiene ningún token de /api.")
            return 0

        if needle is None:
            print(f"Tokens de /api de {email} (fechas en UTC):\n")
            _print_tokens(tokens)
            print("\nPara revocar uno:  revoke_api_token.py <mail> <nombre o id>")
            return 0

        matches = _match(tokens, needle)
        if not matches:
            print(f"Ningún token vivo de {email} coincide con «{needle}». Los que hay:\n")
            _print_tokens(tokens)
            return 1
        if len(matches) > 1:
            print(f"«{needle}» identifica {len(matches)} tokens vivos. Repetilo con el id:\n")
            _print_tokens(matches)
            return 1

        token = matches[0]
        # El nombre y el id se copian a variables **antes** del commit: después la instancia
        # queda expirada, y al salir del `with` la sesión ya está cerrada, así que leer
        # `token.name` para el mensaje sale a buscarlo a la base y levanta
        # `DetachedInstanceError` — un traceback y un exit 1 sobre una revocación que sí
        # ocurrió, que es el error más caro que puede dar este script.
        name, short_id = token.name, str(token.id)[:_ID_CHARS]
        api_token_crud.revoke(db, token)
        db.commit()

    print(f"Revocado «{name}» ({short_id}).")
    print("El próximo request con ese token contesta 401. No se puede deshacer: si era el")
    print("que estaba en uso, hay que emitir otro con create_api_token.py y volver a pegarlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
