"""El alta propia, la confirmación de la dirección y la recuperación de la contraseña.

Lo que estos tests cuidan, por encima de todo, es lo que separa "se anotó" de "ve la
contabilidad": **la cuenta que se crea sola nace apagada**, y apagada no entra. Las pantallas
de esta app no filtran por membresía —`entity_crud.get_all` trae todas las entidades— así que
si esa línea se cae, el registro público pasa a ser una puerta a la contabilidad entera.

Después vienen los dos invariantes de los tokens —de un solo uso, y con vencimiento— y el que
atraviesa las tres pantallas: **ninguna dice si una dirección tiene cuenta acá**.

Nada de acá sale a la red: se parchea `services/email.send_email`, que es el nivel más bajo
con sentido. Los asuntos y los cuerpos se siguen armando de verdad, que es lo que permite
afirmar sobre el link que viaja adentro.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from balance360.crud import email_confirmation as confirmation_crud
from balance360.crud import user as user_crud
from balance360.exceptions import TooManyAttemptsError
from balance360.models.user import User
from balance360.services import password_reset as reset_service
from balance360.services import registration
from balance360.services.security import hash_opaque_token
from tests.factories import make_user

PASSWORD = "una-contrasenia-larga"
OTHER_PASSWORD = "otra-contrasenia-larga"


@pytest.fixture(autouse=True)
def sent_mails(monkeypatch):
    """Intercepta el transporte y devuelve lo que se mandó.

    Autouse a propósito: un test que se olvidara de pedirlo abriría un socket SMTP de verdad y
    fallaría con un timeout de treinta segundos que no tiene nada que ver con lo que estaba
    probando.
    """
    mails: list[dict] = []

    def fake_send(to, subject, body, **kwargs):
        mails.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("balance360.services.email.send_email", fake_send)
    return mails


@pytest.fixture
def registered(db):
    """Una cuenta creada por el circuito público: apagada y sin confirmar."""
    registration.register(
        db, email="nuevo@testing.com.ar", password=PASSWORD, full_name="Alguien Nuevo"
    )
    return user_crud.get_by_email(db, "nuevo@testing.com.ar")


def token_from(mail: dict) -> str:
    """El token que viaja adentro del link del mail.

    Se saca del cuerpo y no de la base a propósito: lo que hay que probar es que el link que le
    llega a la persona **es** el que la app va a aceptar. Leer el token de la fila probaría que
    la fila existe, que no es lo mismo.
    """
    _, _, tail = mail["body"].partition("token=")
    return tail.split()[0]


# --- El alta ------------------------------------------------------------------------------


def test_la_cuenta_que_se_crea_sola_nace_apagada(db, registered):
    """**La línea que sostiene todo lo demás.** Sin esto, registrarse es entrar, y entrar es
    ver la contabilidad de todas las entidades: las pantallas no filtran por membresía."""
    assert registered is not None
    assert registered.is_active is False
    assert registered.email_confirmed_at is None


def test_el_alta_manda_el_link_de_confirmacion(db, sent_mails, registered):
    (mail,) = sent_mails
    assert mail["to"] == ["nuevo@testing.com.ar"]
    assert "/confirm-email?token=" in mail["body"]

    # Y el token del mail resuelve a la fila que se guardó.
    found = confirmation_crud.get_usable_by_hash(db, hash_opaque_token(token_from(mail)))
    assert found is not None and found.user_id == registered.id


def test_la_direccion_se_guarda_normalizada(db, sent_mails):
    """Mayúsculas y espacios: si entraran tal cual, "Miguel@..." y "miguel@..." serían dos
    cuentas para la misma persona y el login encontraría a una sola."""
    registration.register(
        db, email="  MiGuel@Testing.com.AR ", password=PASSWORD, full_name="Miguel"
    )

    assert user_crud.get_by_email(db, "miguel@testing.com.ar") is not None
    assert user_crud.get_by_email(db, "MIGUEL@TESTING.COM.AR") is not None


def test_registrarse_de_nuevo_sobre_una_cuenta_sin_confirmar_no_pisa_la_contrasenia(
    db, sent_mails, registered
):
    """Pisarla sería una toma de cuenta completa: al atacante le alcanzaría con registrarse
    encima de una cuenta pendiente y esperar a que el dueño —que está esperando un mail— abra
    el link que le llegue."""
    registration.register(
        db, email="nuevo@testing.com.ar", password=OTHER_PASSWORD, full_name="Otro"
    )

    db.refresh(registered)
    assert user_crud.verify_user_password(registered, PASSWORD)
    assert not user_crud.verify_user_password(registered, OTHER_PASSWORD)
    # Pero sí sale un link nuevo: el que no encontró el primer mail tiene que poder pedir otro.
    assert len(sent_mails) == 2
    assert "/confirm-email?token=" in sent_mails[1]["body"]


def test_registrarse_sobre_una_cuenta_confirmada_no_crea_otra_ni_delata_nada(
    db, sent_mails, registered
):
    """La pantalla dice lo mismo que en las otras dos ramas; el único que se entera de que la
    cuenta ya existía es el dueño de la casilla, que es quien tiene derecho a saberlo."""
    registration.confirm(db, token_from(sent_mails[0]))
    sent_mails.clear()

    registration.register(
        db, email="nuevo@testing.com.ar", password=OTHER_PASSWORD, full_name="Otro"
    )

    assert db.query(User).filter(User.email == "nuevo@testing.com.ar").count() == 1
    (mail,) = sent_mails
    assert "Ya tenés una cuenta" in mail["subject"]
    assert "/confirm-email?token=" not in mail["body"]


def test_el_alta_se_corta_despues_de_cinco_intentos(db):
    for _ in range(5):
        registration.register(
            db, email="repetido@testing.com.ar", password=PASSWORD, full_name="Alguien"
        )

    with pytest.raises(TooManyAttemptsError):
        registration.register(
            db, email="repetido@testing.com.ar", password=PASSWORD, full_name="Alguien"
        )


# --- La confirmación ----------------------------------------------------------------------


def test_confirmar_marca_la_direccion_pero_no_habilita_la_cuenta(db, sent_mails, registered):
    """Confirmar prueba que la casilla es suya. Habilitar es una decisión de una persona."""
    user = registration.confirm(db, token_from(sent_mails[0]))

    assert user is not None
    assert user.email_confirmed_at is not None
    assert user.is_active is False


def test_el_link_de_confirmacion_se_usa_una_sola_vez(db, sent_mails, registered):
    token = token_from(sent_mails[0])
    assert registration.confirm(db, token) is not None

    assert registration.confirm(db, token) is None


def test_un_token_inventado_o_vencido_da_lo_mismo_que_uno_usado(db, sent_mails, registered):
    """Los cuatro casos se colapsan en `None` en el CRUD, así que el router no puede
    distinguirlos ni por descuido: el remedio de todos es pedir uno nuevo."""
    assert registration.confirm(db, "no-existe") is None

    confirmation = confirmation_crud.get_usable_by_hash(
        db, hash_opaque_token(token_from(sent_mails[0]))
    )
    assert confirmation is not None
    confirmation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()

    assert registration.confirm(db, token_from(sent_mails[0])) is None


# --- La recuperación ----------------------------------------------------------------------


@pytest.fixture
def account(db):
    """Un usuario habilitado, con una contraseña de verdad: el factory guarda un hash de
    mentira y `verify` no lo puede leer."""
    user = make_user(db, email="dueño@testing.com.ar")
    user.hashed_password = user_crud.hash_password(PASSWORD)
    db.commit()
    db.refresh(user)
    return user


def test_pedir_el_reset_manda_el_link(db, sent_mails, account):
    reset_service.request(db, account.email)

    (mail,) = sent_mails
    assert mail["to"] == [account.email]
    assert "/reset-password?token=" in mail["body"]


def test_una_direccion_sin_cuenta_tambien_recibe_un_mail(db, sent_mails):
    """No es una cortesía: si esta rama no mandara nada, sería la única que no puede fallar por
    un problema de SMTP, y ese error pasaría a significar "esa dirección tiene cuenta acá"."""
    reset_service.request(db, "nadie@testing.com.ar")

    (mail,) = sent_mails
    assert mail["to"] == ["nadie@testing.com.ar"]
    assert "no encontramos ninguna cuenta" in mail["body"]


def test_usar_el_link_cambia_la_contrasenia_y_confirma_la_direccion(db, sent_mails, account):
    """Confirma porque haber abierto el link prueba lo mismo que prueba el de confirmación: que
    quien lo abrió tiene la casilla."""
    reset_service.request(db, account.email)
    user = reset_service.consume(db, token_from(sent_mails[0]), OTHER_PASSWORD)

    assert user is not None
    db.refresh(account)
    assert user_crud.verify_user_password(account, OTHER_PASSWORD)
    assert account.email_confirmed_at is not None


def test_el_link_de_reset_se_usa_una_sola_vez(db, sent_mails, account):
    reset_service.request(db, account.email)
    token = token_from(sent_mails[0])

    assert reset_service.consume(db, token, OTHER_PASSWORD) is not None
    assert reset_service.consume(db, token, "tercera-contrasenia") is None


def test_usar_un_link_apaga_los_demas(db, sent_mails, account):
    """Dos links de reset vivos son dos oportunidades de cambiar la contraseña, y la segunda le
    queda a quien pidió la primera."""
    reset_service.request(db, account.email)
    reset_service.request(db, account.email)
    primero, segundo = (token_from(mail) for mail in sent_mails[:2])

    assert reset_service.consume(db, segundo, OTHER_PASSWORD) is not None
    assert reset_service.consume(db, primero, "tercera-contrasenia") is None


def test_el_reset_avisa_a_la_casilla_que_la_contrasenia_cambio(db, sent_mails, account):
    """Es la única señal que le llega al dueño si el reset lo pidió otro — y llega a un lugar
    al que ese otro ya no puede volver, porque el link se consumió."""
    reset_service.request(db, account.email)
    token = token_from(sent_mails[0])
    sent_mails.clear()

    reset_service.consume(db, token, OTHER_PASSWORD)

    (mail,) = sent_mails
    assert "cambió" in mail["subject"]
    assert mail["to"] == [account.email]


def test_el_reset_no_habilita_una_cuenta_apagada(db, sent_mails, registered):
    """Recuperar la contraseña de una cuenta que todavía no habilitaron es válido —el que se
    equivocó al registrarse necesita esa salida— pero no abre la puerta."""
    reset_service.request(db, registered.email)
    reset_service.consume(db, token_from(sent_mails[-1]), OTHER_PASSWORD)

    db.refresh(registered)
    assert registered.is_active is False


# --- Por HTTP -----------------------------------------------------------------------------


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from balance360.dependencies import get_db
    from balance360.main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_una_cuenta_apagada_no_entra_y_se_le_dice_por_que(client, db, registered):
    """Con la contraseña correcta sí se le cuenta qué pasa: ya demostró que la cuenta es suya,
    y "email o contraseña incorrectos" lo mandaría a cambiar una que está bien."""
    response = client.post(
        "/login/", data={"email": registered.email, "password": PASSWORD}, follow_redirects=False
    )

    assert response.status_code == 200  # el formulario de vuelta, no el redirect al dashboard
    assert "todavía no está habilitada" in response.text
    assert "access_token" not in response.cookies


def test_una_contrasenia_que_no_es_dice_lo_mismo_que_un_mail_que_no_existe(client, account):
    inexistente = client.post(
        "/login/", data={"email": "nadie@testing.com.ar", "password": PASSWORD}
    )
    equivocada = client.post("/login/", data={"email": account.email, "password": "otra"})

    assert "Email o contraseña incorrectos" in inexistente.text
    assert "Email o contraseña incorrectos" in equivocada.text


def test_la_cuenta_habilitada_entra(client, account):
    response = client.post(
        "/login/", data={"email": account.email, "password": PASSWORD}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.cookies.get("access_token")


def test_desactivar_a_alguien_lo_saca_en_el_request_siguiente(client, db, account):
    """La cookie es un JWT que vive ocho horas y no hay fila que revocar: sin el chequeo de
    `is_active` en `get_current_user`, apagar una cuenta no la saca hasta que venza sola."""
    client.post("/login/", data={"email": account.email, "password": PASSWORD})
    account.is_active = False
    db.flush()

    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login/"


def test_el_registro_por_http_termina_siempre_en_la_misma_pantalla(client, db, sent_mails):
    nueva = client.post(
        "/register",
        data={
            "full_name": "Alguien Nuevo",
            "email": "http@testing.com.ar",
            "password": PASSWORD,
        },
    )
    repetida = client.post(
        "/register",
        data={
            "full_name": "Alguien Nuevo",
            "email": "http@testing.com.ar",
            "password": PASSWORD,
        },
    )

    assert nueva.status_code == 200 and repetida.status_code == 200
    assert "Revisá tu casilla" in nueva.text
    assert "Revisá tu casilla" in repetida.text


def test_una_contrasenia_corta_no_crea_nada(client, db):
    response = client.post(
        "/register",
        data={"full_name": "Alguien", "email": "corta@testing.com.ar", "password": "abc"},
    )

    assert "al menos" in response.text
    assert user_crud.get_by_email(db, "corta@testing.com.ar") is None


def test_el_link_de_reset_abre_el_formulario_sin_consumirlo(client, db, sent_mails, account):
    reset_service.request(db, account.email)
    token = token_from(sent_mails[0])

    abierto = client.get(f"/reset-password?token={token}")
    assert abierto.status_code == 200
    assert account.email in abierto.text

    # Y sigue sirviendo: abrir el mail no puede quemar el permiso.
    guardado = client.post(
        "/reset-password",
        data={"token": token, "password": OTHER_PASSWORD, "password_confirm": OTHER_PASSWORD},
    )
    assert "Contraseña cambiada" in guardado.text


def test_un_link_de_reset_que_no_sirve_lo_dice_y_no_pide_una_contrasenia(client):
    response = client.get(f"/reset-password?token={uuid.uuid4().hex}")

    assert response.status_code == 400
    assert "ya no sirve" in response.text
    assert 'name="password"' not in response.text
