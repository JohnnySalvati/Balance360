"""Entrada y salida de `POST /api/tokens`.

La contraseña **entra y no sale**, y el token **sale una sola vez**: no hay ningún otro
endpoint que devuelva un token, porque de la fila solo queda el hash. Si se pierde el texto
plano, lo que corresponde es pedir otro, no recuperar este.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ApiTokenIssue(BaseModel):
    """Las credenciales de una persona, a cambio de una credencial de máquina.

    `name` es obligatorio y no tiene default. Es lo único que después permite revocar el
    correcto cuando hay más de uno, y un default —"API", "cliente"— haría que todas las
    integraciones se llamaran igual justo el día que hay que apagar una sola. Se corta en 50
    porque esa es la columna.
    """

    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=50)


class ApiTokenIssued(BaseModel):
    """El token recién emitido. **Es la única vez que existe en claro.**"""

    token: str
    name: str
    created_at: datetime
    # `True` si al emitir este se revocó el anterior con el mismo nombre. El que llama lo
    # necesita para decirle al usuario que el token viejo dejó de andar: si tenía la
    # integración puesta en otro lado, se acaba de caer, y enterarse cuando falle es peor.
    replaced_previous: bool
