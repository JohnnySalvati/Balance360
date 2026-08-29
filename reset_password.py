"""Cambia la contraseña de un usuario desde el servidor. Se corre a mano.

    uv run python reset_password.py miguelsalvati@gmail.com

Pide la contraseña nueva por consola —no se pasa como argumento, para que no quede en el
historial del shell ni en la lista de procesos— y la escribe hasheada.

**Es la salida de emergencia, no el camino normal.** El camino normal es «Olvidé mi contraseña»
en la pantalla de ingreso, que manda un link por mail y no necesita a nadie del otro lado. Este
script existe para los dos casos en los que ese circuito no alcanza:

- el mail no está configurado o no sale, y hay alguien afuera;
- la dirección de la cuenta ya no existe, así que el link no le llegaría a nadie.

Pasó de verdad: el navegador guarda las contraseñas por dominio y FactuMov y Balance360 viven
las dos en `*.insoft.net.ar`, así que guardar la de una encima de la otra dejó a Johnny afuera
de esta. En ese momento la única salida era que otro usuario entrara a Configuración → Usuarios
y la cambiara — o sea que recuperar la cuenta propia dependía de que hubiera alguien más
adentro.

Del lado del servidor y no una pantalla, por lo mismo que `create_api_token.py`: lo corre quien
ya tiene acceso a la base, que es quien ya podría cambiar la contraseña con un UPDATE.
"""

import getpass
import sys

from balance360.crud import user as user_crud
from balance360.database import SessionLocal
from balance360.services.security import PASSWORD_MIN_LENGTH


def main() -> int:
    if len(sys.argv) != 2:
        print("uso: uv run python reset_password.py <mail>")
        return 2

    email = sys.argv[1]

    with SessionLocal() as db:
        user = user_crud.get_by_email(db, email)
        if user is None:
            # Acá sí se dice que no existe, al revés que en las pantallas: no hay nada que
            # ocultarle a quien ya tiene la base delante, y "no pasó nada" lo dejaría buscando
            # el error en la contraseña que acaba de escribir.
            print(f"No hay ningún usuario con la dirección {email}.")
            return 1

        print(f"Usuario: {user.full_name} <{user.email}>")
        password = getpass.getpass("Contraseña nueva: ")
        if len(password) < PASSWORD_MIN_LENGTH:
            print(f"Tiene que tener al menos {PASSWORD_MIN_LENGTH} caracteres.")
            return 1
        if password != getpass.getpass("Repetila: "):
            # Se pide dos veces porque `getpass` no muestra lo que se escribe: sin la
            # confirmación, un dedo torcido deja la cuenta con una contraseña que no sabe nadie
            # y hay que volver a correr esto para enterarse.
            print("No coinciden.")
            return 1

        user_crud.set_password(db, user, password)
        db.commit()

    print("Listo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
