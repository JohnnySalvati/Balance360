"""Ninguna ruta literal queda tapada por una parametrizada.

FastAPI resuelve en orden de declaracion, no de mas especifica a menos
especifica. Una ruta literal como /invoices/close-modal declarada DESPUES de
/invoices/{invoice_id} nunca se alcanza: el segmento entra por el parametro,
falla al parsearse como UUID y sale un 422.

Fue un bug real del modal de envio por mail. Con el 422 HTMX no hace swap
—solo swapea con 2xx— asi que el modal quedaba abierto y cada clic en la X o en
Cancelar repetia el error en vez de cerrarlo.

El test recorre la aplicacion entera y no solo el caso conocido: el mismo error
se puede repetir en cualquier router que agregue una ruta literal al final.
"""

import pytest
from starlette.routing import Route

from balance360.main import app


def _rutas_literales() -> list[tuple[Route, str]]:
    """Cada ruta sin parametros, con cada uno de sus metodos."""
    return [
        (route, method)
        for route in app.routes
        if isinstance(route, Route) and "{" not in route.path
        for method in sorted(route.methods or set())
        if method not in ("HEAD", "OPTIONS")
    ]


def _resuelve(path: str, method: str) -> Route | None:
    """La ruta que Starlette elige para ese path y metodo, en orden real."""
    scope = {"type": "http", "method": method, "path": path, "headers": []}
    for route in app.routes:
        match, _ = route.matches(scope)
        if match.name == "FULL":
            return route
    return None


@pytest.mark.parametrize(
    "route, method",
    _rutas_literales(),
    ids=lambda v: v if isinstance(v, str) else v.path,
)
def test_ruta_literal_no_la_tapa_un_path_param(route, method):
    ganadora = _resuelve(route.path, method)
    assert ganadora is route, (
        f"{method} {route.path} lo resuelve "
        f"{ganadora.path if ganadora else 'ninguna ruta'}: hay que declararlo "
        f"antes de la ruta con parametro"
    )
