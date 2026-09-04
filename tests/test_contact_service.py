"""El CUIT de un contacto no se repite.

Dos capas independientes, y las dos se prueban: la del servicio, que es la que produce un
mensaje que se puede leer, y la del índice único, que es la que aguanta cuando dos requests
concurrentes pasan los dos por la validación antes de que cualquiera de los dos inserte.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from balance360.crud import contact as contact_crud
from balance360.enums import CondicionIva, ContactType, DocType
from balance360.exceptions import ContactDuplicateTaxIdError
from balance360.models.contact import Contact
from balance360.schemas.contact import ContactCreate, ContactUpdate
from balance360.services import contact as contact_service
from tests import factories

AOMA = "30503218107"


def _create_data(name="Nuevo", tax_id=AOMA):
    return ContactCreate(
        name=name,
        tax_id=tax_id,
        contact_type=ContactType.customer,
        condicion_iva=CondicionIva.EXENTO,
        doc_type=DocType.CUIT,
    )


def test_create_rechaza_un_cuit_ya_cargado(db):
    factories.make_contact(db, name="Asociacion Obrera Minera Argentina", tax_id=AOMA)

    with pytest.raises(ContactDuplicateTaxIdError) as excinfo:
        contact_service.create(db, _create_data(name="AOMA Bs. As."))

    # El mensaje tiene que nombrar al que ya está: es lo único que le dice al usuario dónde
    # está el contacto que debería usar.
    assert "Asociacion Obrera Minera Argentina" in str(excinfo.value)
    assert "30-50321810-7" in str(excinfo.value)


def test_create_compara_por_digitos_y_no_por_texto(db):
    """El CUIT con guiones es el mismo CUIT.

    Es el camino por el que entró el duplicado real: el segundo alta se tipeó formateado y la
    comparación textual contra el guardado sin guiones no encontró nada.
    """
    factories.make_contact(db, name="Ya cargado", tax_id=AOMA)

    with pytest.raises(ContactDuplicateTaxIdError):
        contact_service.create(db, _create_data(tax_id="30-50321810-7"))


def test_create_permite_varios_contactos_sin_cuit(db):
    """Sin CUIT no hay nada que sea único: son todos consumidores finales distintos."""
    primero = contact_service.create(db, _create_data(name="Chelo", tax_id=None))
    segundo = contact_service.create(db, _create_data(name="Tomy", tax_id=None))

    assert primero.tax_id is None
    assert segundo.tax_id is None
    assert primero.id != segundo.id


def test_create_normaliza_el_cuit_vacio_a_null(db):
    """`""` no es NULL: dos cadenas vacías chocarían contra el índice."""
    primero = contact_service.create(db, _create_data(name="Uno", tax_id=""))
    segundo = contact_service.create(db, _create_data(name="Dos", tax_id=""))

    assert primero.tax_id is None
    assert segundo.tax_id is None


def test_update_no_choca_contra_si_mismo(db):
    """Guardar otro campo sin tocar el CUIT tiene que seguir funcionando.

    Sin `exclude_id`, la validación encontraría al propio contacto y ninguna edición pasaría.
    """
    contact = factories.make_contact(db, name="AOMA", tax_id=AOMA)

    updated = contact_service.update(db, contact, ContactUpdate(name="AOMA Bs. As.", tax_id=AOMA))

    assert updated.name == "AOMA Bs. As."
    assert updated.tax_id == AOMA


def test_update_rechaza_el_cuit_de_otro(db):
    factories.make_contact(db, name="Asociacion Obrera Minera Argentina", tax_id=AOMA)
    otro = factories.make_contact(db, name="Otro cliente", tax_id="20111111112")

    with pytest.raises(ContactDuplicateTaxIdError):
        contact_service.update(db, otro, ContactUpdate(tax_id=AOMA))


def test_update_sin_tax_id_no_valida_nada(db):
    """Un PATCH que no manda el campo no lo está cambiando."""
    contact = factories.make_contact(db, name="AOMA", tax_id=AOMA)

    updated = contact_service.update(db, contact, ContactUpdate(name="AOMA Bs. As."))

    assert updated.tax_id == AOMA


def test_el_indice_unico_frena_lo_que_esquiva_al_servicio(db):
    """La garantía de verdad está en la base, no en el `if`.

    Escribir por `crud` salteando el servicio es lo que hace cualquier script suelto, y es lo
    que harían dos requests que validan a la vez antes de que ninguno haya insertado.
    """
    factories.make_contact(db, name="Ya cargado", tax_id=AOMA)

    db.add(
        Contact(
            name="Duplicado",
            tax_id=AOMA,
            contact_type=ContactType.customer,
            condicion_iva=CondicionIva.EXENTO,
            doc_type=DocType.CUIT,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_get_by_tax_id_encuentra_al_unico(db):
    """Con el índice puesto, el `.first()` de `get_by_tax_id` ya no elige entre dos.

    Es la función que resuelve el receptor de lo que llega de FactuMov y el proveedor de un
    PDF importado; con duplicados devolvía cualquiera de los dos.
    """
    contact = factories.make_contact(db, name="Asociacion Obrera", tax_id=AOMA)

    assert contact_crud.get_by_tax_id(db, "30-50321810-7") == contact
    assert contact_crud.get_by_tax_id(db, AOMA, exclude_id=contact.id) is None
