"""Parseo de la respuesta del padron de ARCA.

La forma de los objetos sale del WSDL de personaServiceA5, asi que se arman con
SimpleNamespace en vez de golpear la red: lo que se prueba es el mapeo a Contact,
que es donde estan las decisiones (que es el nombre, como se arma el domicilio y
de donde sale la condicion frente al IVA).
"""

import re
from types import SimpleNamespace

import pytest

from balance360.enums import CondicionIva, ContactType, DocType
from balance360.exceptions import PadronError
from balance360.services.padron import (
    ADDRESS_MAX_LENGTH,
    IVA_EXENTO,
    IVA_INSCRIPTO,
    Taxpayer,
    get_taxpayer,
    to_taxpayer,
)
from balance360.web.templating import templates
from tests import factories

CUIT = "30500010012"


def _domicilio(
    direccion="Av. Siempreviva 742", localidad="Rosario", provincia="Santa Fe", cp="2000"
):
    return SimpleNamespace(
        direccion=direccion,
        localidad=localidad,
        descripcionProvincia=provincia,
        codPostal=cp,
    )


def _response(
    razon_social=None,
    nombre=None,
    apellido=None,
    domicilio=None,
    impuestos=(),
    monotributo=None,
    estado="ACTIVO",
):
    return SimpleNamespace(
        datosGenerales=SimpleNamespace(
            razonSocial=razon_social,
            nombre=nombre,
            apellido=apellido,
            domicilioFiscal=domicilio,
            estadoClave=estado,
        ),
        datosRegimenGeneral=SimpleNamespace(
            impuesto=[SimpleNamespace(idImpuesto=i) for i in impuestos]
        ),
        datosMonotributo=monotributo,
    )


def test_persona_juridica_inscripta():
    taxpayer = to_taxpayer(
        CUIT, _response(razon_social="VENEX SA", domicilio=_domicilio(), impuestos=[IVA_INSCRIPTO])
    )

    assert taxpayer.tax_id == CUIT
    assert taxpayer.name == "VENEX SA"
    assert taxpayer.address == "Av. Siempreviva 742, Rosario, Santa Fe, CP 2000"
    assert taxpayer.condicion_iva == CondicionIva.INSCRIPTO
    assert taxpayer.active


def test_persona_fisica_monotributista():
    taxpayer = to_taxpayer(
        CUIT,
        _response(
            nombre="Jose Miguel",
            apellido="Salvati",
            domicilio=_domicilio(),
            monotributo=SimpleNamespace(categoriaMonotributo=None),
        ),
    )

    assert taxpayer.name == "Jose Miguel Salvati"
    assert taxpayer.condicion_iva == CondicionIva.MONOTRIBUTO


def test_monotributo_gana_sobre_los_impuestos():
    """El monotributista tambien puede traer impuestos en regimen general."""
    taxpayer = to_taxpayer(
        CUIT,
        _response(
            razon_social="Kiosco SRL",
            impuestos=[IVA_INSCRIPTO],
            monotributo=SimpleNamespace(categoriaMonotributo=None),
        ),
    )

    assert taxpayer.condicion_iva == CondicionIva.MONOTRIBUTO


def test_exento():
    taxpayer = to_taxpayer(CUIT, _response(razon_social="Fundacion", impuestos=[IVA_EXENTO]))

    assert taxpayer.condicion_iva == CondicionIva.EXENTO


def test_sin_impuestos_de_iva_es_consumidor_final():
    taxpayer = to_taxpayer(CUIT, _response(razon_social="Alguien", impuestos=[301]))

    assert taxpayer.condicion_iva == CondicionIva.FINAL


def test_clave_inactiva():
    taxpayer = to_taxpayer(CUIT, _response(razon_social="Baja SA", estado="INACTIVO"))

    assert not taxpayer.active


def test_provincia_repetida_no_se_duplica():
    """CABA viene como localidad y como provincia."""
    taxpayer = to_taxpayer(
        CUIT,
        _response(
            razon_social="Portenia SA",
            domicilio=_domicilio(
                localidad="CIUDAD AUTONOMA BUENOS AIRES",
                provincia="ciudad autonoma buenos aires",
                cp="1000",
            ),
        ),
    )

    assert taxpayer.address == "Av. Siempreviva 742, CIUDAD AUTONOMA BUENOS AIRES, CP 1000"


def test_domicilio_se_recorta_al_largo_de_la_columna():
    taxpayer = to_taxpayer(
        CUIT, _response(razon_social="Larga SA", domicilio=_domicilio(direccion="x" * 400))
    )

    assert taxpayer.address is not None
    assert len(taxpayer.address) == ADDRESS_MAX_LENGTH


def test_sin_domicilio():
    taxpayer = to_taxpayer(CUIT, _response(razon_social="Sin Domicilio SA", domicilio=None))

    assert taxpayer.address is None


def test_sin_datos_generales():
    response = SimpleNamespace(datosGenerales=None)

    with pytest.raises(PadronError):
        to_taxpayer(CUIT, response)


def test_cuit_invalido_no_llama_a_arca(monkeypatch):
    """La validacion de largo va antes del ticket: sin red y sin ticket inutil."""

    def _boom(service):
        raise AssertionError("no se deberia pedir un ticket con un CUIT invalido")

    monkeypatch.setattr("balance360.services.padron.get_access_ticket", _boom)

    with pytest.raises(PadronError):
        get_taxpayer("2018281")


# ── Render de los templates que usan el padron ──────────────────────────────


def _render(name, **context):
    return templates.env.get_template(name).render(**context)


def _modal(contact=None):
    return _render(
        "config/contacts/_form_modal.html",
        contact=contact,
        contact_type=ContactType,
        condicion_iva=CondicionIva,
        doc_type=DocType,
    )


def test_el_alta_de_contacto_trae_el_boton_del_padron():
    html = _modal()

    assert 'hx-get="/config/contacts/padron"' in html
    assert 'hx-include="#contact-tax-id"' in html
    assert 'id="padron-status"' in html


def test_el_modal_no_preselecciona_condicion_en_un_alta():
    """El include comparte el `selected` del {% set %}: sin contacto no hay elegida."""
    assert "selected" not in _selected_options(_modal())


def test_el_modal_preselecciona_la_condicion_al_editar(db):
    contact = factories.make_contact(db, condicion_iva=CondicionIva.MONOTRIBUTO)

    assert _selected_options(_modal(contact)) == ["MONOTRIBUTO"]


def _selected_options(html):
    select = re.search(r'<select[^>]*id="contact-condicion-iva".*?</select>', html, re.S)
    assert select, "no se encontro el select de condicion IVA"
    return re.findall(r'<option value="([^"]*)"\s+selected', select.group(0))


def test_el_resultado_del_padron_reemplaza_los_tres_campos():
    taxpayer = Taxpayer(
        tax_id=CUIT,
        name="VENEX SA",
        address="Av. Siempreviva 742, Rosario",
        condicion_iva=CondicionIva.INSCRIPTO,
        active=True,
    )

    html = _render(
        "config/contacts/_padron_result.html", taxpayer=taxpayer, condicion_iva=CondicionIva
    )

    assert html.count('hx-swap-oob="true"') == 3
    for control_id in ("contact-name", "contact-condicion-iva", "contact-address"):
        assert f'id="{control_id}"' in html
    assert 'value="VENEX SA"' in html
    assert 'value="Av. Siempreviva 742, Rosario"' in html
    assert _selected_options(html) == ["INSCRIPTO"]
    assert "INACTIVA" not in html


def test_el_resultado_avisa_cuando_la_clave_esta_inactiva():
    taxpayer = Taxpayer(
        tax_id=CUIT,
        name="Baja SA",
        address=None,
        condicion_iva=CondicionIva.FINAL,
        active=False,
    )

    html = _render(
        "config/contacts/_padron_result.html", taxpayer=taxpayer, condicion_iva=CondicionIva
    )

    assert "INACTIVA" in html
    assert 'value=""' in html
