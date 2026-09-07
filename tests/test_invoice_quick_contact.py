"""El alta de contacto desde el propio comprobante.

Cargar una compra con un proveedor que todavia no esta en la base obligaba a irse a
Configuracion → Contactos, crearlo y volver a empezar el comprobante. El "+ Nuevo" del
select abre el MISMO modal de Configuracion —con su boton de padron— y solo le cambia a
donde postea; el contacto nuevo vuelve por HX-Trigger y lo mete en el select el listener
`contactCreated` de static/js/invoice_form.js.

Lo que se prueba aca es el contrato entre esas tres piezas: el boton apunta al modal, el
modal postea a la ruta del comprobante, y la ruta devuelve exactamente los campos que la
opcion del select necesita (`data-type` y `data-condicion`, que deciden si la opcion se ve
y que letra se admite).
"""

import json
import re
import uuid

import pytest

from balance360.crud import contact as contact_crud
from balance360.enums import (
    Concepto,
    CondicionIva,
    ContactType,
    DocType,
    InvoiceType,
    VoucherType,
)
from balance360.web.templating import templates
from tests import factories


def _render_header(invoice=None, contacts=()):
    template = templates.env.get_template("invoices/partials/_header_fields.html")
    return template.render(
        invoice=invoice,
        entities=[],
        contacts=list(contacts),
        categories=[],
        fiscal_identities=[],
        selected_fiscal_identity_id=None,
        invoice_type=InvoiceType,
        voucher_type=VoucherType,
        concepto=Concepto,
    )


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


def test_el_encabezado_ofrece_crear_un_contacto():
    """El boton vive en el partial compartido, asi que sale igual en el alta y en la edicion."""
    html = _render_header()

    assert 'hx-get="/invoices/contact-form"' in html
    assert 'hx-target="#modal"' in html


def test_el_alta_tiene_el_modal_fuera_del_formulario(client):
    """El modal trae su propio <form> y el navegador descarta los formularios anidados: si el
    #modal quedara adentro del <form> del comprobante, el alta de contacto no postearia nada.

    Se mira el HTML de la pagina entera y no el partial porque el contenedor lo pone la pagina:
    es lo que se puede olvidar al agregar una tercera que incluya el encabezado."""
    html = client.get("/invoices/new").text
    formulario = re.search(r'<form hx-post="/invoices/".*?</form>', html, re.S)

    assert '<div id="modal"></div>' in html
    assert formulario and 'id="modal"' not in formulario.group(0)
    assert "/invoices/contact-form" in formulario.group(0)  # el boton si va adentro


def test_la_edicion_del_encabezado_tambien_tiene_donde_abrir_el_modal(client, db):
    """El detalle ya traia un #modal para el envio por mail; el "+ Nuevo" del encabezado en
    modo edicion apunta al mismo."""
    invoice = factories.make_invoice(db)

    assert '<div id="modal"></div>' in client.get(f"/invoices/{invoice.id}").text


def test_el_modal_del_comprobante_postea_a_la_ruta_del_comprobante(client):
    """Y no a /config/contacts/, que refresca una tabla que en el comprobante no existe."""
    html = client.get("/invoices/contact-form").text

    assert 'hx-post="/invoices/contacts"' in html
    assert 'hx-get="/config/contacts/padron"' in html  # el boton de padron viene incluido


@pytest.mark.parametrize(
    "invoice_type, expected",
    [("purchase", "supplier"), ("sale", "customer")],
)
def test_el_tipo_viene_preseleccionado_segun_el_comprobante(client, invoice_type, expected):
    """Crear el contacto del tipo que no corresponde lo dejaria oculto en el select justo
    despues de haberlo creado: filterContacts esconde las opciones del otro tipo."""
    html = client.get("/invoices/contact-form", params={"invoice_type": invoice_type}).text

    selected = re.search(r'<option value="([^"]+)" selected>', html)
    assert selected and selected.group(1) == expected


def test_crear_el_contacto_devuelve_lo_que_el_select_necesita(client, db):
    response = client.post(
        "/invoices/contacts",
        data={
            "name": "Proveedor Nuevo",
            "tax_id": "30-50321810-7",
            "contact_type": "supplier",
            "condicion_iva": "INSCRIPTO",
            "doc_type": "CUIT",
        },
    )

    assert response.status_code == 200
    assert response.text == '<div id="modal"></div>'  # el modal se cierra

    payload = json.loads(response.headers["HX-Trigger"])["contactCreated"]
    assert payload["name"] == "Proveedor Nuevo"
    # data-type y data-condicion: el primero decide si la opcion se ve en este
    # comprobante, el segundo que letras admite applyVoucherFilter.
    assert payload["contact_type"] == "supplier"
    assert payload["condicion_iva"] == "INSCRIPTO"

    creado = contact_crud.get_by_id(db, uuid.UUID(payload["id"]))
    assert creado is not None
    assert creado.tax_id == "30503218107"  # normalizado por ContactCreate
    assert creado.contact_type is ContactType.supplier
    assert creado.condicion_iva is CondicionIva.INSCRIPTO
    assert creado.doc_type is DocType.CUIT


def test_el_cuit_repetido_no_crea_nada_y_deja_el_modal_abierto(client, db):
    """El servicio ya prohibe el CUIT duplicado; lo que importa aca es que el error salga
    como toast con HX-Reswap: none, porque si swapeara se llevaria puesto el modal y con el
    lo que el usuario acababa de tipear."""
    existente = factories.make_contact(db, name="AOMA Bs. As.", tax_id="30503218107")

    response = client.post(
        "/invoices/contacts",
        data={
            "name": "Asociacion Obrera Minera Argentina",
            "tax_id": "30503218107",
            "contact_type": "supplier",
            "condicion_iva": "INSCRIPTO",
            "doc_type": "CUIT",
        },
        headers={"HX-Request": "true"},  # el handler global decide toast o HTML por este header
    )

    assert response.status_code == 200
    assert response.headers["HX-Reswap"] == "none"
    assert existente.name in json.loads(response.headers["HX-Trigger"])["showToast"]["message"]
