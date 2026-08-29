"""La emisión de un token de `/api` a cambio de mail y contraseña.

Lo que estos tests cuidan es que la única puerta de la app que acepta una contraseña sin
sesión previa no se pueda usar para averiguar contraseñas: que el presupuesto de intentos se
gaste con los fallidos —si solo contara los exitosos no defendería nada—, que sea por cuenta
y no global, y que el mensaje de "no" sea el mismo tanto para un mail que no existe como para
una contraseña equivocada.

El otro invariante es el de higiene: emitir un token apaga el anterior de la misma
integración. Los tokens no caducan, así que cada reconexión que no revoque deja viva una
credencial de escritura que nadie usa y que nadie va a acordarse de apagar.
"""

import pytest

from balance360.crud import api_token as api_token_crud
from balance360.crud import user as user_crud
from balance360.exceptions import ApiTokenAuthError, TooManyAttemptsError
from balance360.services import api_token as service
from balance360.services.rate_limit import RateLimiter
from tests.factories import make_user

PASSWORD = "una-contrasenia-larga"


@pytest.fixture
def account(db):
    """Un usuario con una contraseña de verdad: el factory guarda un hash de mentira y
    `verify` no lo puede leer."""
    user = make_user(db)
    user.hashed_password = user_crud.hash_password(PASSWORD)
    db.commit()
    db.refresh(user)
    return user


def issue(db, account, password=PASSWORD, name="FactuMov"):
    return service.issue_for_credentials(db, email=account.email, password=password, name=name)


def test_las_credenciales_correctas_devuelven_un_token_que_despues_sirve(db, account):
    issued = issue(db, account)

    assert issued.token.startswith(service.TOKEN_PREFIX)
    assert issued.replaced_previous is False

    # El viaje de vuelta: el token en claro tiene que resolver a la fila por el mismo camino
    # que usa cada request de `/api`. Que se haya creado una fila no prueba que sirva.
    found = api_token_crud.get_active_by_hash(db, service.hash_token(issued.token))
    assert found is not None
    assert found.user_id == account.id


def test_el_token_no_queda_en_claro_en_la_base(db, account):
    issued = issue(db, account)

    found = api_token_crud.get_active_by_hash(db, service.hash_token(issued.token))
    assert found is not None
    assert issued.token not in found.token_hash


def test_una_contrasenia_equivocada_no_emite_nada(db, account):
    with pytest.raises(ApiTokenAuthError):
        issue(db, account, password="otra cosa")

    assert api_token_crud.get_all_for_user(db, account.id) == []


def test_un_mail_que_no_existe_da_el_mismo_mensaje_que_una_contrasenia_mala(db, account):
    with pytest.raises(ApiTokenAuthError) as sin_cuenta:
        service.issue_for_credentials(
            db, email="nadie@testing.com.ar", password=PASSWORD, name="FactuMov"
        )
    with pytest.raises(ApiTokenAuthError) as mal_password:
        issue(db, account, password="otra cosa")

    # Dos mensajes distintos convertirían el endpoint en una lista de qué direcciones tienen
    # cuenta acá, que es exactamente lo que no puede contestar algo abierto a internet.
    assert str(sin_cuenta.value) == str(mal_password.value)


def test_una_cuenta_desactivada_no_emite_aunque_la_contrasenia_este_bien(db, account):
    account.is_active = False
    db.commit()

    with pytest.raises(ApiTokenAuthError) as error:
        issue(db, account)

    # Acá sí se dice qué pasa: quien llegó hasta este punto ya demostró que la contraseña es
    # suya, y "mail o contraseña incorrectos" lo mandaría a cambiar una que está bien.
    assert "desactivada" in str(error.value)
    assert api_token_crud.get_all_for_user(db, account.id) == []


def test_emitir_de_nuevo_revoca_el_anterior_de_la_misma_integracion(db, account):
    primero = issue(db, account)
    segundo = issue(db, account)

    assert segundo.replaced_previous is True
    assert api_token_crud.get_active_by_hash(db, service.hash_token(primero.token)) is None
    assert api_token_crud.get_active_by_hash(db, service.hash_token(segundo.token)) is not None


def test_emitir_no_toca_los_tokens_de_otra_integracion(db, account):
    otro = issue(db, account, name="Un script")
    issue(db, account, name="FactuMov")

    # Reemplazar es por integración y no por usuario: apagar todo lo que la persona tenga
    # emitido porque conectó FactuMov le rompería lo demás sin avisarle.
    assert api_token_crud.get_active_by_hash(db, service.hash_token(otro.token)) is not None


def test_los_intentos_fallidos_gastan_el_presupuesto(db, account):
    for _ in range(5):
        with pytest.raises(ApiTokenAuthError):
            issue(db, account, password="otra cosa")

    # El sexto ya no llega a mirar la contraseña, y por eso el que se corta es el que la tiene
    # bien: si el límite solo contara los intentos exitosos no defendería absolutamente nada.
    with pytest.raises(TooManyAttemptsError):
        issue(db, account)


def test_el_limite_es_por_cuenta_y_no_global(db, account):
    otra = make_user(db)
    otra.hashed_password = user_crud.hash_password(PASSWORD)
    db.commit()

    for _ in range(6):
        with pytest.raises((ApiTokenAuthError, TooManyAttemptsError)):
            issue(db, account, password="otra cosa")

    # Que a una cuenta la estén atacando no puede dejar afuera al resto. Es lo mismo que hace
    # que la clave sea el mail y no la IP: por IP, todos los usuarios de FactuMov comparten
    # la del servidor y el primero que se pasa los saca a todos.
    assert issue(db, otra).token


def test_el_error_de_limite_dice_cuanto_falta(db, account):
    for _ in range(5):
        with pytest.raises(ApiTokenAuthError):
            issue(db, account, password="otra cosa")

    with pytest.raises(TooManyAttemptsError) as error:
        issue(db, account)

    assert 0 < error.value.retry_after <= 15 * 60


def test_la_ventana_se_libera_cuando_pasa_el_tiempo():
    """Sobre el limitador pelado y con el reloj inyectado: la ventana real es de un cuarto de
    hora y el test no puede dormir eso."""
    now = 0.0
    limiter = RateLimiter(limit=2, window_seconds=60, clock=lambda: now)

    assert limiter.check("alguien@testing.com.ar") is None
    assert limiter.check("alguien@testing.com.ar") is None
    assert limiter.check("alguien@testing.com.ar") is not None

    now = 61.0
    assert limiter.check("alguien@testing.com.ar") is None


@pytest.fixture
def client(db):
    """El endpoint por HTTP, con la sesión del test.

    Es el único test de esta app que levanta la app entera, y es a propósito: lo que se
    prueba acá no está en el router ni en el servicio, sino en los handlers de `main.py` —que
    `/api` conteste JSON y no el HTML del login, y que el 429 traiga el `Retry-After`—. Todo
    lo demás se prueba contra el servicio, que es donde están las decisiones.
    """
    from fastapi.testclient import TestClient

    from balance360.dependencies import get_db
    from balance360.main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def body(account, password=PASSWORD, name="FactuMov"):
    return {"email": account.email, "password": password, "name": name}


def test_el_endpoint_devuelve_el_token_una_vez(client, account):
    response = client.post("/api/tokens", json=body(account))

    assert response.status_code == 201
    payload = response.json()
    assert payload["token"].startswith(service.TOKEN_PREFIX)
    assert payload["name"] == "FactuMov"
    assert payload["replaced_previous"] is False


def test_el_endpoint_no_pide_credencial_para_dar_una(client, account):
    """Sin `Authorization` ni cookie. Es el único de `/api` que se monta sin `get_api_user`:
    pedirle credencial sería pedir lo que todavía no se tiene."""
    response = client.post("/api/tokens", json=body(account))

    assert response.status_code == 201


def test_las_credenciales_que_no_son_contestan_401_en_json(client, account):
    response = client.post("/api/tokens", json=body(account, password="otra cosa"))

    # JSON y no el redirect al login: un cliente HTTP que sigue el 307 recibe el HTML con
    # status 200 y cree que le dieron un token.
    assert response.status_code == 401
    assert "incorrectos" in response.json()["detail"]


def test_pasarse_del_limite_contesta_429_con_retry_after(client, account):
    for _ in range(5):
        client.post("/api/tokens", json=body(account, password="otra cosa"))

    response = client.post("/api/tokens", json=body(account))

    assert response.status_code == 429
    # Sin este header el cliente reintenta enseguida y se gasta el resto de la ventana en
    # pedidos que ya sabemos que van a fallar.
    assert int(response.headers["Retry-After"]) > 0
