import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from balance360.crud import arca_ticket as arca_ticket_crud
from balance360.models.arca_ticket import ArcaTicket
from balance360.services import arca

SERVICE = "wsfe"


@pytest.fixture
def arca_db(db, monkeypatch, tmp_path):
    """Apunta la sesión propia de get_access_ticket a la conexión del test.

    get_access_ticket abre su propio SessionLocal a propósito (ver su docstring),
    así que sin esto el test escribiría en la base de desarrollo.

    También aparta el archivo legacy: en el repo hay un ticket_arca.json real, y
    sin apartarlo los tests lo adoptarían y no probarían lo que dicen probar.
    """
    factory = sessionmaker(bind=db.connection(), join_transaction_mode="create_savepoint")
    monkeypatch.setattr(arca, "SessionLocal", factory)
    monkeypatch.setattr(arca, "LEGACY_TICKET_FILE", str(tmp_path / "no-existe.json"))
    return db


@pytest.fixture
def arca_db_conexion_propia(engine, monkeypatch, tmp_path):
    """Como arca_db pero con una conexión de verdad, separada de la del test.

    Hace falta para probar el aislamiento transaccional: con las dos sesiones sobre
    la misma conexión, el rollback del test deshace también lo que commiteó la
    sesión de adentro, que es justo lo contrario de lo que pasa en producción.

    Como acá se escribe de verdad, la limpieza es explícita: el rollback del fixture
    `db` no alcanza para borrar filas commiteadas en otra conexión.
    """
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(arca, "SessionLocal", factory)
    monkeypatch.setattr(arca, "LEGACY_TICKET_FILE", str(tmp_path / "no-existe.json"))

    yield factory

    with factory() as limpieza:
        limpieza.execute(delete(ArcaTicket))
        limpieza.commit()


@pytest.fixture
def wsaa(monkeypatch):
    """Doble de WSAA que cuenta cuántas veces se lo llamó."""
    llamadas = []

    def fake_arca_query(service: str) -> dict:
        llamadas.append(service)
        expiration = datetime.now(timezone.utc) + timedelta(hours=12)
        return {
            "service": service,
            "token": f"token-{len(llamadas)}",
            "sign": f"sign-{len(llamadas)}",
            "expiration_time": expiration.isoformat(),
        }

    monkeypatch.setattr(arca, "arca_query", fake_arca_query)
    return llamadas


def _guardar(db, expiration_time, token="viejo", sign="firma-vieja"):
    arca_ticket_crud.save(
        db,
        env=arca.settings.afip_env,
        service=SERVICE,
        token=token,
        sign=sign,
        expiration_time=expiration_time,
    )
    db.commit()


def test_sin_ticket_lo_pide_y_lo_guarda(arca_db, wsaa):
    ticket = arca.get_access_ticket(SERVICE)

    assert wsaa == [SERVICE]
    assert ticket["token"] == "token-1"

    guardado = arca_ticket_crud.get(arca_db, arca.settings.afip_env, SERVICE)
    assert guardado is not None
    assert guardado.token == "token-1"


def test_con_ticket_vigente_no_llama_a_wsaa(arca_db, wsaa):
    _guardar(arca_db, datetime.now(timezone.utc) + timedelta(hours=6))

    ticket = arca.get_access_ticket(SERVICE)

    assert wsaa == []
    assert ticket["token"] == "viejo"


def test_ticket_vencido_se_renueva(arca_db, wsaa):
    _guardar(arca_db, datetime.now(timezone.utc) - timedelta(minutes=1))

    ticket = arca.get_access_ticket(SERVICE)

    assert wsaa == [SERVICE]
    assert ticket["token"] == "token-1"


def test_el_margen_evita_usar_uno_que_vence_ya(arca_db, wsaa):
    """Un ticket que vence en 1 minuto no sirve: la llamada a ARCA tarda más que eso."""
    _guardar(arca_db, datetime.now(timezone.utc) + timedelta(minutes=1))

    arca.get_access_ticket(SERVICE)

    assert wsaa == [SERVICE]


def test_el_segundo_pedido_reusa_el_del_primero(arca_db, wsaa):
    arca.get_access_ticket(SERVICE)
    segundo = arca.get_access_ticket(SERVICE)

    assert wsaa == [SERVICE]
    assert segundo["token"] == "token-1"


def test_el_ticket_queda_guardado_aunque_el_que_lo_pidio_falle(arca_db_conexion_propia, db, wsaa):
    """El motivo de que get_access_ticket abra su propia sesión.

    Si el ticket viajara en la transacción de la factura, un error de validación lo
    revertiría junto con ella y WSAA no emitiría otro por ~12 h.
    """
    ticket = arca.get_access_ticket(SERVICE)

    db.rollback()  # la operación que pidió el ticket termina en rollback

    with arca_db_conexion_propia() as otra_sesion:
        guardado = arca_ticket_crud.get(otra_sesion, arca.settings.afip_env, SERVICE)
        assert guardado is not None
        assert guardado.token == ticket["token"]


def test_cada_servicio_tiene_su_ticket(arca_db, wsaa):
    arca.get_access_ticket(SERVICE)
    arca.get_access_ticket("ws_sr_constancia_inscripcion")

    assert wsaa == [SERVICE, "ws_sr_constancia_inscripcion"]
    assert arca_ticket_crud.get(arca_db, arca.settings.afip_env, SERVICE) is not None
    assert (
        arca_ticket_crud.get(arca_db, arca.settings.afip_env, "ws_sr_constancia_inscripcion")
        is not None
    )


def test_los_tickets_de_homo_y_prod_no_se_mezclan(arca_db, wsaa, monkeypatch):
    """Un ticket de homologación no sirve para producción: son CUIT y firmas distintos."""
    monkeypatch.setattr(arca.settings, "afip_env", "homo")
    homo = arca.get_access_ticket(SERVICE)

    monkeypatch.setattr(arca.settings, "afip_env", "prod")
    prod = arca.get_access_ticket(SERVICE)

    assert wsaa == [SERVICE, SERVICE]
    assert homo["token"] != prod["token"]
    assert arca_ticket_crud.get(arca_db, "homo", SERVICE) is not None
    assert arca_ticket_crud.get(arca_db, "prod", SERVICE) is not None


def _escribir_legacy(tmp_path, monkeypatch, expiration_time):
    archivo = tmp_path / "ticket_arca.json"
    archivo.write_text(
        json.dumps(
            {
                f"{arca.settings.afip_env}:{SERVICE}": {
                    "service": SERVICE,
                    "token": "del-archivo",
                    "sign": "firma-del-archivo",
                    "expiration_time": expiration_time.isoformat(),
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(arca, "LEGACY_TICKET_FILE", str(archivo))


def test_adopta_el_ticket_vigente_del_archivo_viejo(arca_db, wsaa, monkeypatch, tmp_path):
    """El deploy que crea la tabla no puede dejar sin facturar por 12 h."""
    _escribir_legacy(tmp_path, monkeypatch, datetime.now(timezone.utc) + timedelta(hours=6))

    ticket = arca.get_access_ticket(SERVICE)

    assert wsaa == []
    assert ticket["token"] == "del-archivo"

    guardado = arca_ticket_crud.get(arca_db, arca.settings.afip_env, SERVICE)
    assert guardado is not None
    assert guardado.token == "del-archivo"


def test_no_adopta_un_ticket_vencido_del_archivo(arca_db, wsaa, monkeypatch, tmp_path):
    _escribir_legacy(tmp_path, monkeypatch, datetime.now(timezone.utc) - timedelta(hours=1))

    ticket = arca.get_access_ticket(SERVICE)

    assert wsaa == [SERVICE]
    assert ticket["token"] == "token-1"


def test_un_archivo_ilegible_no_rompe_nada(arca_db, wsaa, monkeypatch, tmp_path):
    archivo = tmp_path / "ticket_arca.json"
    archivo.write_text("{no es json", encoding="utf-8")
    monkeypatch.setattr(arca, "LEGACY_TICKET_FILE", str(archivo))

    ticket = arca.get_access_ticket(SERVICE)

    assert ticket["token"] == "token-1"


def test_una_respuesta_incompleta_de_wsaa_no_se_cachea():
    """findtext devuelve None si falta el tag; antes ese None se guardaba igual."""
    xml = "<loginTicketResponse><credentials><token>abc</token></credentials></loginTicketResponse>"

    with pytest.raises(arca.WsaaError):
        arca.parse_xml(xml, SERVICE)
