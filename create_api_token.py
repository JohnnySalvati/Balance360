"""Emite un token de `/api` para un usuario. Se corre a mano, una vez por integración.

    uv run python create_api_token.py miguelsalvati@gmail.com FactuMov

**El token sale por pantalla una sola vez.** Después queda el hash y no hay forma de
recuperarlo: si se pierde, se emite otro y se revoca el viejo. Es un script y no una pantalla
por la misma razón por la que lo es `create_user_script.py` — se usa una vez cada mucho, del
lado del servidor, por quien ya tiene acceso a la base.
"""

import sys

from balance360.crud import api_token as api_token_crud
from balance360.crud import user as user_crud
from balance360.database import SessionLocal
from balance360.services.api_token import generate_token, hash_token


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    email, name = sys.argv[1], sys.argv[2]

    with SessionLocal() as db:
        user = user_crud.get_by_email(db, email)
        if user is None:
            print(f"No hay ningún usuario con el mail {email}.")
            return 1

        token = generate_token()
        api_token_crud.create(db, user_id=user.id, name=name, token_hash=hash_token(token))
        db.commit()

    print(f"Token para {email} ({name}):\n\n    {token}\n")
    print("Guardalo ahora: no se puede volver a ver.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
