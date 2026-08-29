"""La puerta por la que una integración se consigue su propia credencial.

Es el **único router de `/api` que se monta sin autenticación**, y tiene que ser así: es el
que autentica. Lo que lo separa de un login es lo que devuelve — no una sesión para navegar,
sino un token de máquina que se revoca solo, que no arrastra la contraseña y que deja escrito
quién entró (`api_tokens.name`, `last_used_at`).

Existe porque la alternativa era peor de las dos formas. Emitir el token a mano con
`create_api_token.py` obliga a entrar por ssh al servidor cada vez que alguien quiere conectar
FactuMov, o sea que la integración no la puede usar nadie que no sea el que administra la VM.
Y que FactuMov guardara la contraseña de cada usuario para hacer login como ellos es
exactamente el escenario que `models/api_token.py` describe como el motivo por el que los
tokens existen.

Acá la contraseña la escribe el usuario, viaja una vez, y lo que queda guardado del otro lado
es el token.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from balance360.dependencies import get_db
from balance360.schemas.api_token import ApiTokenIssue, ApiTokenIssued
from balance360.services import api_token as api_token_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tokens", tags=["api-tokens"])


@router.post("", response_model=ApiTokenIssued, status_code=201)
def issue_api_token(data: ApiTokenIssue, db: Session = Depends(get_db)) -> ApiTokenIssued:
    """Emite un token para el usuario dueño de esas credenciales.

    Los errores —credenciales que no son, cuenta desactivada, demasiados intentos— suben como
    `Balance360Error` y los convierte el handler global de `main.py`, que para `/api` responde
    JSON con el status del error. Atraparlos acá para reescribirlos sería perder lo único que
    el otro lado le puede mostrar al usuario: si tiene que corregir la contraseña o esperar.

    Del log sale el mail, que es lo que después permite reconstruir quién pidió qué. **No sale
    ni la contraseña ni el token**: un secreto en un archivo de log es un secreto filtrado, y
    los logs se copian a lugares a los que la base no llega.
    """
    issued = api_token_service.issue_for_credentials(
        db, email=data.email, password=data.password, name=data.name
    )

    logger.info(
        "Emitido un token de API para %s (%s)%s.",
        data.email,
        data.name,
        " reemplazando al anterior" if issued.replaced_previous else "",
    )
    return ApiTokenIssued(
        token=issued.token,
        name=issued.api_token.name,
        created_at=issued.api_token.created_at,
        replaced_previous=issued.replaced_previous,
    )
