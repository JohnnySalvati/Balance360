import logging
from html import escape
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi import Request as FastAPIRequest
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from balance360.dependencies import get_api_user, get_current_user
from balance360.exceptions import ArcaError, Balance360Error
from balance360.models import (  # noqa: F401
    account,
    api_token,
    attachment,
    category,
    contact,
    currency,
    entity,
    import_rule,
    transaction,
    user,
)
from balance360.routers import (
    account,
    api_token,
    category,
    contact,
    currency,
    entity,
    exchange_rate,
    import_rule,
    issued_invoice,
    transaction,
    user,
)
from balance360.web import auth
from balance360.web import router as web_router
from balance360.web.responses import toast_error

logger = logging.getLogger(__name__)

app = FastAPI(title="Balance360")

static_files = StaticFiles(directory=Path(__file__).parent / "static")

app.mount(path="/static", app=static_files, name="static")

# Todo `/api` pide credencial. Hasta acá no pedía ninguna: los routers JSON se montaban
# pelados y solo `web_router` llevaba `Depends(get_current_user)`, así que cualquiera que
# supiera la URL leía y escribía contactos, cuentas y transacciones sin loguearse.
#
# `get_api_user` acepta el token de máquina o la cookie de sesión — ver su docstring—, así
# que esto no rompe nada de lo que ya funcionaba desde el navegador.
API_AUTH = [Depends(get_api_user)]

# **La excepción, y la única.** `/api/tokens` es el endpoint que emite la credencial con la
# que se entra a todo lo demás: pedirle credencial sería pedir lo que todavía no se tiene.
# Autentica con mail y contraseña, y por eso es el único de la app con límite de intentos —
# ver `services/rate_limit.py`.
app.include_router(api_token.router, prefix="/api")

app.include_router(category.router, prefix="/api", dependencies=API_AUTH)
app.include_router(currency.router, prefix="/api", dependencies=API_AUTH)
app.include_router(contact.router, prefix="/api", dependencies=API_AUTH)
app.include_router(account.router, prefix="/api", dependencies=API_AUTH)
app.include_router(entity.router, prefix="/api", dependencies=API_AUTH)
app.include_router(user.router, prefix="/api", dependencies=API_AUTH)
app.include_router(transaction.router, prefix="/api", dependencies=API_AUTH)
app.include_router(exchange_rate.router, prefix="/api", dependencies=API_AUTH)
app.include_router(import_rule.router, prefix="/api", dependencies=API_AUTH)
app.include_router(issued_invoice.router, prefix="/api", dependencies=API_AUTH)
app.include_router(web_router.router, dependencies=[Depends(get_current_user)])
app.include_router(auth.router)
# Sin `get_current_user`, igual que el de arriba: son las pantallas que se usan justamente
# cuando no hay sesión —crear cuenta, confirmar la dirección, recuperar la contraseña—.
app.include_router(auth.public_router)


@app.exception_handler(401)
async def unauthorized_handler(request: FastAPIRequest, exc):
    """Sin sesión: al login si es un navegador, 401 si es la API.

    El redirect es lo correcto para una persona que abrió una URL con la sesión vencida. Para
    un cliente HTTP es lo peor que puede pasar: `requests` sigue el 307, recibe el HTML del
    login con status 200 y la integración da por registrado un comprobante que nunca se
    registró. Un 401 con cuerpo JSON es lo que deja que el otro lado se entere.
    """
    if request.url.path.startswith("/api"):
        return JSONResponse({"detail": "No autenticado"}, status_code=401)
    return RedirectResponse(url="/login/")


@app.exception_handler(Balance360Error)
async def balance360_error_handler(request: FastAPIRequest, exc: Balance360Error):
    if isinstance(exc, ArcaError):
        logger.error("%s %s — %s", request.method, request.url.path, exc, exc_info=exc)
    else:
        logger.warning("%s %s — %s: %s", request.method, request.url.path, type(exc).__name__, exc)

    # `/api` contesta JSON con el status del error, y no el HTML de más abajo. Un cliente
    # HTTP que recibe `<h1>No se pudo completar…` no tiene de dónde sacar el motivo, y con
    # 400 fijo tampoco puede distinguir "esto se arregla y reintentás" de "esto ya estaba".
    if request.url.path.startswith("/api"):
        # `Retry-After` cuando el error trae con qué armarlo. Un 429 pelado no le dice al
        # cliente cuánto esperar, así que reintenta enseguida y se gasta el resto de la
        # ventana en pedidos que ya sabemos que van a fallar. Segundos enteros y redondeando
        # para arriba: un `Retry-After: 0` invita a reintentar de inmediato.
        retry_after = getattr(exc, "retry_after", None)
        headers = {"Retry-After": str(int(retry_after) + 1)} if retry_after is not None else None
        return JSONResponse({"detail": str(exc)}, status_code=exc.status, headers=headers)

    if request.headers.get("HX-Request"):
        return toast_error(str(exc))
    return HTMLResponse(
        f"<h1>No se pudo completar la operación</h1><p>{escape(str(exc))}</p>",
        status_code=400,
    )
