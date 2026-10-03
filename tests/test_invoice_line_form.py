"""La fila en blanco para cargar items esta siempre puesta.

Antes habia un "+ Agregar item" que traia el formulario y un ✕ que lo cerraba. Cargar
items es justo lo que se va a hacer en esa pantalla, asi que el click previo era un paso
de mas. Ahora la fila es parte de partials/items_table.html: el POST de una linea
devuelve la tabla entera, y con ella una fila nueva en blanco para el item siguiente.

Lo que NO cambio es de que formulario cuelga. Los controles de la fila llevan
`form="new-line-form"` —el <form> vive fuera de la tabla, porque un <form> dentro de un
<table> lo descarta el parser— que es un formulario distinto del que confirma el
comprobante. Por eso lo que quede escrito y no se agregue se descarta solo.

Para saber si la fila esta se busca su `id="line-form-row"`, no el texto
`form="new-line-form"`: ese texto tambien aparece en el JS de la pagina (el selector
`[form="new-line-form"]` de recalcNewLineSubtotal), que se emite este o no la fila, y
contra el la ausencia nunca se cumple y la presencia se cumple siempre.
"""

import pytest

from balance360.enums import IvaAliquot
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


def test_el_detalle_ya_trae_la_fila_en_blanco(client, db):
    invoice = factories.make_invoice(db)

    html = client.get(f"/invoices/{invoice.id}").text

    assert 'id="line-form-row"' in html
    assert "Agregar item" not in html and "Agregar ítem" not in html


def test_agregar_un_item_devuelve_otra_fila_en_blanco(client, db):
    """Es lo que reemplaza al boton: la tabla que vuelve ya tiene donde cargar el
    siguiente."""
    invoice = factories.make_invoice(db)

    response = client.post(
        f"/invoices/{invoice.id}/lines",
        data={
            "description": "Flete",
            "quantity": "1",
            "unit_price": "1000",
            "iva_aliquot": IvaAliquot.exempt.name,
        },
    )

    assert response.status_code == 200
    assert "Flete" in response.text
    assert 'id="line-form-row"' in response.text


def test_la_fila_ofrece_el_catalogo_en_cada_render(client, db):
    """La fila trae el select de productos y la sugerencia de precio, que antes se
    armaban en la unica ruta que servia el formulario. Si una de las rutas que devuelven
    la tabla se olvida del contexto, la fila sale sin productos."""
    producto = factories.make_product(db, name="Cable UTP")
    invoice = factories.make_invoice(db)

    response = client.post(
        f"/invoices/{invoice.id}/lines",
        data={
            "description": "Flete",
            "quantity": "1",
            "unit_price": "1000",
            "iva_aliquot": IvaAliquot.exempt.name,
        },
    )

    assert str(producto.id) in response.text
    assert "Cable UTP" in response.text


def test_un_comprobante_confirmado_no_tiene_fila_de_alta(client, db):
    """Confirmado el comprobante es una ficha: las lineas estan congeladas."""
    invoice = factories.make_invoice(db)
    factories.make_invoice_line(db, invoice_id=invoice.id)
    invoice.confirmed = True
    db.commit()

    html = client.get(f"/invoices/{invoice.id}").text

    assert 'id="line-form-row"' not in html


def test_los_controles_de_la_fila_no_son_del_formulario_que_confirma(client, db):
    """Es lo que hace que la fila vacia se descarte sola. Sin el atributo `form=`, los
    campos pertenecerian al <form> que los contiene y viajarian con el."""
    invoice = factories.make_invoice(db)

    html = client.get(f"/invoices/{invoice.id}").text
    fila = html[html.index('id="line-form-row"') : html.index("</tfoot>")]

    assert fila.count('form="new-line-form"') >= 4
    for control in ("product_id", "description", "quantity", "unit_price"):
        assert f'name="{control}"' in fila
