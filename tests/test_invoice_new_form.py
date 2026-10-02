"""El alta de un comprobante nace con lo que se estaba mirando en la lista.

Se entra a Comprobantes, se elige la solapa (compras o ventas) y una entidad, y recien
ahi se toca "+ Nuevo": el tipo y la entidad del comprobante que se va a cargar ya estan
dichos. Volver a elegirlos es repetir lo mismo, y elegir distinto por descuido manda el
comprobante al balance equivocado.

El link los arrastra en la query (newInvoiceUrl en invoices/list.html, que los lee de la
URL porque los filtros se aplican con hx-push-url). La ruta los valida contra lo que
existe: son parametros que cualquiera puede escribir a mano.
"""

import re
import uuid

import pytest

from tests import factories


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from balance360.dependencies import get_current_user, get_db
    from balance360.main import app

    user = factories.make_user(db)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _selected(html: str, select_name: str) -> str | None:
    """El value de la opcion marcada dentro de ese <select>."""
    bloque = re.search(rf'<select name="{select_name}".*?</select>', html, re.S)
    assert bloque, f"no esta el select {select_name}"
    marcada = re.search(r'<option value="([^"]*)"\s*\n?\s*selected', bloque.group(0))
    return marcada.group(1) if marcada else None


@pytest.mark.parametrize("invoice_type", ["sale", "purchase"])
def test_el_tipo_viene_de_la_solapa(client, db, invoice_type):
    factories.make_entity(db)

    html = client.get("/invoices/new", params={"invoice_type": invoice_type}).text

    assert _selected(html, "invoice_type") == invoice_type


def test_la_entidad_viene_del_filtro(client, db):
    factories.make_entity(db, name="InSoft")
    irigoyen = factories.make_entity(db, name="Irigoyen")

    html = client.get("/invoices/new", params={"entity_id": str(irigoyen.id)}).text

    assert _selected(html, "entity_id") == str(irigoyen.id)


def test_una_entidad_que_no_existe_no_rompe_el_alta(client, db):
    """La query se puede escribir a mano. Cae en la primera, que es lo que se mostraba
    antes de que el link arrastrara nada."""
    factories.make_entity(db, name="InSoft")

    response = client.get("/invoices/new", params={"entity_id": str(uuid.uuid4())})

    assert response.status_code == 200
    assert _selected(response.text, "entity_id") is not None


def test_sin_parametros_no_marca_nada(client, db):
    """Entrar por /invoices/new directo tiene que seguir funcionando como antes: sin
    opcion marcada, el navegador elige la primera."""
    factories.make_entity(db)

    html = client.get("/invoices/new").text

    assert _selected(html, "invoice_type") is None


def test_el_boton_de_la_lista_arrastra_los_filtros(client, db):
    """El link se arma en el navegador, con los mismos valores que la solapa."""
    html = client.get("/invoices/", params={"invoice_type": "sale"}).text

    assert "newInvoiceUrl()" in html
    assert "/invoices/new" in html
