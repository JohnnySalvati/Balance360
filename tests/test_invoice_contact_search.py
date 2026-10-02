"""El buscador de contactos del encabezado de un comprobante.

Elegir el contacto era recorrer un <select> con la libreta entera. El buscador lo
resuelve el SERVIDOR (GET /invoices/contact-options) y no el navegador: es el mismo
`contact_crud.get_all(db, search)` —ilike sobre nombre Y nombre de fantasia— que usa
Configuracion → Contactos, asi que "buscar un contacto" significa lo mismo en los dos
lugares en vez de tener un criterio por pantalla.

La ruta devuelve las <option> del #contact-select y HTMX le reemplaza el contenido. Lo
que se prueba aca es lo que decide esa respuesta: que encuentre por fantasia, que no
ofrezca proveedores en una venta, que deje algo elegido (un select cerrado solo muestra
la opcion elegida: sin eso el buscador se ve igual que si no hiciera nada) y que no se
lleve puesto el contacto que ya estaba elegido.
"""

import pytest

from balance360.enums import ContactType
from balance360.web.templating import templates
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


def _options(client, **params):
    response = client.get("/invoices/contact-options", params=params)
    assert response.status_code == 200
    return response.text


def test_encuentra_por_nombre_de_fantasia(client, db):
    """El caso que lo motivo: el mismo sujeto esta cargado con su razon social y se lo
    busca por como se lo nombra todos los dias."""
    aoma = factories.make_contact(
        db, name="Asociacion Obrera Minera Argentina", trade_name="AOMA Bs. As."
    )
    otro = factories.make_contact(db, name="Zeta SA")

    html = _options(client, search="aoma")

    assert str(aoma.id) in html
    assert str(otro.id) not in html


@pytest.mark.parametrize("escrito", ["asociacion", "Asociación", "ASOCIACION", "minería"])
def test_las_tildes_no_cambian_lo_que_encuentra(client, db, escrito):
    """Los nombres reales estan escritos con tilde y nadie la escribe al buscar. Se
    normalizan las DOS puntas: buscar "Asociación" tal cual tiene que seguir andando."""
    aoma = factories.make_contact(db, name="Asociación Obrera Minería Argentina")

    assert str(aoma.id) in _options(client, search=escrito)


def test_no_ofrece_proveedores_en_una_venta(client, db):
    """El tipo viaja en el pedido (hx-include del #invoice-type) y lo filtra la ruta: el
    select que se devuelve ya no pasa por filterContacts."""
    cliente = factories.make_contact(db, name="Cliente", contact_type=ContactType.customer)
    proveedor = factories.make_contact(db, name="Proveedor", contact_type=ContactType.supplier)
    ambos = factories.make_contact(db, name="Ambos", contact_type=ContactType.both)

    html = _options(client, invoice_type="sale")

    assert str(cliente.id) in html
    assert str(ambos.id) in html
    assert str(proveedor.id) not in html


def test_deja_elegido_el_primer_resultado(client, db):
    """Un <select> cerrado muestra solo lo elegido, asi que filtrar opciones que no
    estan a la vista no se ve. Moviendo la seleccion el efecto se nota sin abrir la
    lista. No se guarda nada: el encabezado se envia aparte."""
    contacto = factories.make_contact(db, name="Zeta SA")

    html = _options(client, search="zeta")

    assert f'value="{contacto.id}"' in html
    assert html.count("selected") == 1
    assert "Seleccionar contacto" not in html  # ya hay algo elegido


def test_el_contacto_ya_elegido_vuelve_aunque_no_coincida(client, db):
    """Si no, un tipeo equivocado lo borraria del comprobante y habria que volver a
    buscarlo."""
    elegido = factories.make_contact(db, name="Zeta SA")

    html = _options(client, search="no-existe-nada-asi", contact_id=str(elegido.id))

    assert f'value="{elegido.id}"' in html
    assert "selected" in html


def test_sin_texto_vuelve_la_libreta_entera_y_respeta_lo_elegido(client, db):
    """Borrar el buscador tiene que deshacer el filtro, no dejar la lista corta."""
    elegido = factories.make_contact(db, name="Zeta SA")
    otro = factories.make_contact(db, name="Alfa SA")

    html = _options(client, search="", contact_id=str(elegido.id))

    assert str(otro.id) in html
    assert f'value="{elegido.id}" data-type="{elegido.contact_type.value}"' in html
    assert html.count("selected") == 1


def test_sin_nada_elegido_queda_el_placeholder(client, db):
    """El `required` del select es lo que obliga a decidir en el alta."""
    factories.make_contact(db, name="Zeta SA")

    assert "Seleccionar contacto" in _options(client)


def test_la_opcion_lleva_lo_que_deciden_el_filtro_y_la_letra(client, db):
    """`data-type` decide si la opcion se ve en este comprobante y `data-condicion` que
    letras admite applyVoucherFilter. Son el contrato con el JS del encabezado."""
    contacto = factories.make_contact(db, name="Zeta SA", contact_type=ContactType.customer)

    html = _options(client, search="zeta")

    assert 'data-type="customer"' in html
    assert f'data-condicion="{contacto.condicion_iva.name}"' in html


def test_el_encabezado_apunta_al_buscador():
    """El input no filtra en el navegador: pide las opciones y se las deja al select."""
    html = templates.env.get_template("invoices/partials/_header_fields.html").render(
        invoice=None,
        entities=[],
        contacts=[],
        categories=[],
        fiscal_identities=[],
        selected_fiscal_identity_id=None,
        invoice_type=[],
        voucher_type=[],
        concepto=[],
    )

    assert 'hx-get="/invoices/contact-options"' in html
    assert 'hx-target="#contact-select"' in html
    # Manda el tipo de comprobante y lo ya elegido, o la ruta no puede filtrar ni
    # conservar la seleccion.
    assert 'hx-include="#invoice-type, #contact-select"' in html
