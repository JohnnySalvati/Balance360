"""El registro de un comprobante que emitió FactuMov.

Lo que estos tests cuidan no es el alta —eso lo hace el CRUD de siempre— sino las dos cosas
que la integración puede romper en silencio: que los importes que Balance360 deriva de las
líneas sean los que ARCA autorizó, y que un reintento no duplique un comprobante que ya no se
puede borrar.

El caso de la factura B de $100 al 21% no es un número elegido para que quede lindo: es el que
demuestra por qué `unit_price` tuvo que pasar a cuatro decimales. Con dos, el neto más cercano
da 99,99 y este test falla.
"""

import datetime
import uuid
from decimal import Decimal

import pytest

from balance360.enums import CondicionIva, DocType, IvaAliquot, VoucherType
from balance360.exceptions import (
    IssuedInvoiceConflictError,
    IssuedInvoiceError,
    IssuedInvoiceMismatchError,
)
from balance360.models.invoice import Invoice
from balance360.schemas.issued_invoice import IssuedInvoiceCreate
from balance360.services import issued_invoice as service
from tests.factories import (
    make_contact,
    make_entity,
    make_fiscal_identity,
    make_invoice,
    make_membership,
    make_user,
)

ISSUER_TAX_ID = "20182810674"


@pytest.fixture
def issuer(db):
    """Un usuario con una entidad, y un CUIT asociado a ella. El caso normal."""
    user = make_user(db)
    entity = make_entity(db, name="InSoft")
    make_membership(db, user_id=user.id, entity_id=entity.id)
    identity = make_fiscal_identity(db, name="InSoft SRL", tax_id=ISSUER_TAX_ID)
    identity.entities.append(entity)
    db.commit()
    db.refresh(user)
    return user, entity, identity


def payload(**overrides) -> IssuedInvoiceCreate:
    data = {
        "external_id": uuid.uuid4(),
        "issuer_tax_id": ISSUER_TAX_ID,
        "customer": {
            "name": "Cliente Test",
            "tax_id": "30111111118",
            "doc_type": "CUIT",
            "condicion_iva": "INSCRIPTO",
        },
        "voucher_type": "A",
        "pos": 1,
        "number": 34,
        "date": datetime.date(2026, 8, 28),
        "cae": "86350816969306",
        "cae_expiry": datetime.date(2026, 9, 7),
        "lines": [
            {
                "description": "Desarrollo",
                "quantity": "3",
                "unit_price": "1000.00",
                "iva_aliquot": "standard",
            }
        ],
        "totals": {"net": "3000.00", "iva": "630.00", "total": "3630.00"},
    }
    data.update(overrides)
    return IssuedInvoiceCreate.model_validate(data)


def test_registra_una_a_con_los_importes_que_autorizo_arca(db, issuer):
    user, entity, identity = issuer

    invoice, already = service.register(db, user, payload())

    assert already is False
    assert invoice.entity_id == entity.id
    assert invoice.fiscal_identity_id == identity.id
    # Confirmado y autorizado porque ya pasaron; impago porque el cobro es otro hecho.
    assert (invoice.confirmed, invoice.authorized, invoice.paid) == (True, True, False)
    assert invoice.cae == "86350816969306"
    assert invoice.net_total == Decimal("3000.00")
    assert invoice.total == Decimal("3630.00")


def test_una_a_con_cantidad_entera_conserva_la_cantidad(db, issuer):
    """En la A las dos apps escriben el precio igual, así que la línea se copia tal cual."""
    user, _, _ = issuer

    invoice, _ = service.register(db, user, payload())

    (line,) = invoice.invoice_lines
    assert line.quantity == 3
    assert line.unit_price == Decimal("1000.00")
    assert line.description == "Desarrollo"


def test_una_b_de_cien_pesos_cierra_al_centavo(db, issuer):
    """El caso que obligó a los cuatro decimales: con dos, el total da 99,99.

    FactuMov guarda el precio de una B con el IVA adentro ($100) y acá el unitario es neto.
    El neto exacto es 82,6446…; el mejor de dos decimales, 82,64, vuelve a dar 99,99.
    """
    user, _, _ = issuer

    invoice, _ = service.register(
        db,
        user,
        payload(
            voucher_type="B",
            customer={
                "name": "Consumidor Final",
                "tax_id": None,
                "doc_type": "DNI",
                "condicion_iva": "FINAL",
            },
            lines=[
                {
                    "description": "Servicio",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "iva_aliquot": "standard",
                }
            ],
            totals={"net": "82.64", "iva": "17.36", "total": "100.00"},
        ),
    )

    assert invoice.total == Decimal("100.00")
    assert invoice.net_total == Decimal("82.64")


def test_una_cantidad_fraccionaria_se_colapsa_y_queda_en_la_descripcion(db, issuer):
    """`quantity` es entero acá. Truncar 1,5 facturaría de menos, así que se colapsa a 1."""
    user, _, _ = issuer

    invoice, _ = service.register(
        db,
        user,
        payload(
            lines=[
                {
                    "description": "Consultoría",
                    "quantity": "1.5",
                    "unit_price": "8000.00",
                    "iva_aliquot": "standard",
                }
            ],
            totals={"net": "12000.00", "iva": "2520.00", "total": "14520.00"},
        ),
    )

    (line,) = invoice.invoice_lines
    assert line.quantity == 1
    assert line.unit_price == Decimal("12000.00")
    assert line.description == "Consultoría (1,5 × $8.000)"
    assert invoice.total == Decimal("14520.00")


def test_el_reintento_devuelve_el_mismo_comprobante(db, issuer):
    """Idempotencia por `external_id`: registrar dos veces no duplica nada."""
    user, _, _ = issuer
    data = payload()

    first, first_already = service.register(db, user, data)
    second, second_already = service.register(db, user, data)

    assert first_already is False
    assert second_already is True
    assert first.id == second.id
    assert db.query(Invoice).filter(Invoice.external_id == data.external_id).count() == 1


def test_el_contacto_que_ya_existe_no_se_pisa(db, issuer):
    user, _, _ = issuer
    existing = make_contact(db, name="Cliente Viejo", tax_id="30111111118")

    invoice, _ = service.register(db, user, payload())

    assert invoice.contact_id == existing.id
    assert existing.name == "Cliente Viejo"


def test_el_cuit_que_no_esta_cargado_no_registra_nada(db):
    user = make_user(db)

    with pytest.raises(IssuedInvoiceError, match="no está cargado"):
        service.register(db, user, payload())


def test_el_cuit_de_una_entidad_ajena_no_registra_nada(db):
    """El token actúa como un usuario: sin membresía, no hay entidad candidata."""
    outsider = make_user(db)
    entity = make_entity(db, name="Ajena")
    identity = make_fiscal_identity(db, name="Ajena SRL", tax_id=ISSUER_TAX_ID)
    identity.entities.append(entity)
    db.commit()

    with pytest.raises(IssuedInvoiceError, match="ninguna entidad"):
        service.register(db, outsider, payload())


def test_un_cuit_con_dos_entidades_pide_que_se_elija(db):
    user = make_user(db)
    identity = make_fiscal_identity(db, name="Compartida", tax_id=ISSUER_TAX_ID)
    for name in ("InSoft", "Escuela"):
        entity = make_entity(db, name=name)
        make_membership(db, user_id=user.id, entity_id=entity.id)
        identity.entities.append(entity)
    db.commit()
    db.refresh(user)

    with pytest.raises(IssuedInvoiceError, match="más de una entidad"):
        service.register(db, user, payload())


def test_elegir_la_entidad_resuelve_la_ambiguedad(db):
    user = make_user(db)
    identity = make_fiscal_identity(db, name="Compartida", tax_id=ISSUER_TAX_ID)
    entities = {}
    for name in ("InSoft", "Escuela"):
        entity = make_entity(db, name=name)
        make_membership(db, user_id=user.id, entity_id=entity.id)
        identity.entities.append(entity)
        entities[name] = entity
    db.commit()
    db.refresh(user)

    invoice, _ = service.register(db, user, payload(entity_id=entities["Escuela"].id))

    assert invoice.entity_id == entities["Escuela"].id


def test_un_comprobante_ya_cargado_a_mano_no_se_duplica(db, issuer):
    """Mismo número por otro camino: alguien lo cargó acá antes de conectar las apps."""
    user, entity, identity = issuer
    make_invoice(
        db,
        entity_id=entity.id,
        fiscal_identity_id=identity.id,
        pos=1,
        number=34,
        voucher_type=VoucherType.A,
    )

    with pytest.raises(IssuedInvoiceConflictError, match="ya está cargado"):
        service.register(db, user, payload())


def test_si_los_importes_no_cierran_no_se_guarda(db, issuer):
    """La red de la traducción de precios: mejor sin comprobante que con el total cambiado."""
    user, _, _ = issuer

    with pytest.raises(IssuedInvoiceMismatchError, match="No se registró nada"):
        service.register(db, user, payload(totals={"net": "1.00", "iva": "0.21", "total": "1.21"}))


def test_los_enums_viajan_por_nombre(db, issuer):
    """`FINAL` vale 6 acá y 5 en FactuMov. Por nombre, la diferencia no importa."""
    data = payload(
        voucher_type="B",
        customer={
            "name": "Consumidor Final",
            "tax_id": None,
            "doc_type": "DNI",
            "condicion_iva": "FINAL",
        },
        lines=[
            {
                "description": "Servicio",
                "quantity": "1",
                "unit_price": "100.00",
                "iva_aliquot": "reduced",
            }
        ],
        totals={"net": "90.50", "iva": "9.50", "total": "100.00"},
    )

    assert data.customer.condicion_iva is CondicionIva.FINAL
    assert data.customer.doc_type is DocType.DNI
    assert data.lines[0].iva_aliquot is IvaAliquot.reduced


def test_un_nombre_de_enum_que_no_existe_no_pasa_la_validacion(db):
    with pytest.raises(ValueError, match="no es un valor conocido"):
        payload(
            customer={
                "name": "X",
                "tax_id": None,
                "doc_type": "PASAPORTE",
                "condicion_iva": "INSCRIPTO",
            }
        )
