import base64
import json
import ssl
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timedelta, timezone

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key, pkcs7
from cryptography.x509 import load_pem_x509_certificate
from cryptography.x509.oid import NameOID
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from urllib3.poolmanager import PoolManager
from zeep import Client
from zeep.cache import SqliteCache
from zeep.exceptions import Fault
from zeep.transports import Transport

from balance360.crud import arca_ticket as arca_ticket_crud
from balance360.database import SessionLocal, settings
from balance360.exceptions import ArcaError, WsaaError

WSAA_URL = {
    "homo": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL",
    "prod": "https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL",
}


class _AfipTlsAdapter(HTTPAdapter):
    """Baja el nivel de seguridad de OpenSSL solo para la conexión con AFIP.

    Los servidores de AFIP negocian Diffie-Hellman de 1024 bits, que el OpenSSL
    moderno rechaza por defecto (SECLEVEL 2). SECLEVEL=1 lo permite. NO desactiva
    la verificación del certificado del servidor: solo afloja la fuerza del cifrado.
    """

    def __init__(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        self._ssl_context = ctx
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=self._ssl_context,
        )


def build_client(url: str) -> Client:
    session = requests.Session()
    session.mount("https://", _AfipTlsAdapter())
    transport = Transport(
        session=session,
        timeout=30,
        operation_timeout=30,
        cache=SqliteCache(),
    )
    return Client(url, transport=transport)


TICKET_MARGIN = timedelta(minutes=5)

LEGACY_TICKET_FILE = "ticket_arca.json"


def _lock_key(env: str, service: str) -> int:
    """Clave estable para el advisory lock de Postgres.

    crc32 y no hash(): hash() de un str cambia en cada proceso (PYTHONHASHSEED),
    asi que dos workers calcularian claves distintas y el lock no serviria de nada.
    """
    return zlib.crc32(f"arca-ticket:{env}:{service}".encode())


def _is_usable(expiration_time: datetime) -> bool:
    return expiration_time > datetime.now(timezone.utc) + TICKET_MARGIN


def _as_dict(service: str, token: str, sign: str, expiration_time: datetime) -> dict:
    return {
        "service": service,
        "token": token,
        "sign": sign,
        "expiration_time": expiration_time.isoformat(),
    }


def _adopt_legacy_ticket(db: Session, env: str, service: str) -> dict | None:
    """Rescata a la base un ticket todavia vigente del cache viejo en archivo.

    Existe solo para el deploy que introduce la tabla: el contenedor que se apaga
    se lleva su ticket_arca.json, y sin esto la primera factura despues del deploy
    le pide un ticket nuevo a WSAA, que lo rechaza mientras el anterior siga vivo.
    Se puede borrar cuando ya no queden instalaciones con el archivo.
    """
    try:
        with open(LEGACY_TICKET_FILE, encoding="utf-8") as file:
            tickets = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None

    ticket = tickets.get(f"{env}:{service}") if isinstance(tickets, dict) else None
    if not ticket:
        return None

    try:
        expiration_time = datetime.fromisoformat(ticket["expiration_time"])
    except (KeyError, TypeError, ValueError):
        return None

    if expiration_time.tzinfo is None or not _is_usable(expiration_time):
        return None

    arca_ticket_crud.save(
        db,
        env=env,
        service=service,
        token=ticket["token"],
        sign=ticket["sign"],
        expiration_time=expiration_time,
    )
    return _as_dict(service, ticket["token"], ticket["sign"], expiration_time)


def build_tra(service: str) -> str:
    timestamp = int(datetime.now().timestamp())
    generation_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    expiration_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <loginTicketRequest>
            <header>
                <uniqueId>{timestamp}</uniqueId>
                <generationTime>{generation_time}</generationTime>
                <expirationTime>{expiration_time}</expirationTime>
            </header>
            <service>{service}</service>
        </loginTicketRequest>
        """
    return xml


def sign(xml: str) -> bytes:

    private_key_path = settings.private_key_path
    cert_path = settings.cert_path

    if not cert_path or not private_key_path:
        raise ArcaError("Certificados de ARCA no configurados")

    with open(cert_path, "rb") as cert_file:
        cert_data = cert_file.read()
    cert_key = load_pem_x509_certificate(data=cert_data)

    with open(private_key_path, "rb") as private_key_file:
        private_key_data = private_key_file.read()
    private_key = load_pem_private_key(data=private_key_data, password=None)
    assert isinstance(private_key, RSAPrivateKey)

    builder = pkcs7.PKCS7SignatureBuilder()

    xml_signed = (
        builder.set_data(xml.encode("utf-8"))
        .add_signer(cert_key, private_key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [])
    )
    return xml_signed


def get_certificate_cuit() -> str:
    """El CUIT duenio del certificado, del campo serialNumber del subject.

    Es el mismo que WSAA autoriza, asi que es el que los servicios esperan como
    `cuitRepresentada`. Se lee del certificado y no de una variable de entorno
    justamente para que no puedan quedar en desacuerdo.
    """
    cert_path = settings.cert_path
    if not cert_path:
        raise ArcaError("Certificados de ARCA no configurados")

    with open(cert_path, "rb") as cert_file:
        cert = load_pem_x509_certificate(cert_file.read())

    for attribute in cert.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER):
        digits = "".join(c for c in str(attribute.value) if c.isdigit())
        if len(digits) == 11:
            return digits

    raise ArcaError("El certificado de ARCA no tiene un CUIT en el subject")


def parse_xml(response: str, service: str) -> dict:
    tree = ET.fromstring(response)
    token = tree.findtext(".//token")
    sign = tree.findtext(".//sign")
    expiration_time = tree.findtext(".//expirationTime")

    # findtext devuelve None si el tag no esta. Antes ese None se cacheaba igual y
    # el error recien aparecia al facturar; ahora no llega a guardarse.
    if not token or not sign or not expiration_time:
        raise WsaaError("ARCA: la respuesta de WSAA no trae un ticket completo")

    return {"service": service, "token": token, "sign": sign, "expiration_time": expiration_time}


def arca_query(service: str) -> dict:

    xml = build_tra(service)

    xml_signed = sign(xml)

    try:
        client = build_client(WSAA_URL[settings.afip_env])
        response = client.service.loginCms(in0=base64.b64encode(xml_signed).decode("utf-8"))
    except Fault as e:
        raise WsaaError(f"ARCA: {e}") from e
    except RequestException as e:
        raise ArcaError("No se puede conectar con ARCA, reintenta en unos minutos") from e
    return parse_xml(response, service)


def get_access_ticket(service: str) -> dict:
    """Devuelve un ticket vigente, del cache o pidiendoselo a WSAA.

    Abre su propia sesion a proposito, en vez de recibir el `db` del que llama. El
    ticket tiene que quedar guardado aunque la operacion que lo pidio termine en
    rollback: si viajara en la transaccion de la factura, un error de validacion la
    revertiria junto con el ticket, y WSAA no emite otro por ~12 h. El cache seria
    peor que no tenerlo.

    El advisory lock cubre el otro lado del mismo problema: sin el, dos pedidos
    simultaneos con el ticket vencido le piden uno a WSAA cada uno, y el segundo se
    come "el CEE ya posee un TA valido". El primero que entra lo trae y lo guarda;
    el segundo espera y se encuentra el ticket ya hecho.
    """
    env = settings.afip_env

    with SessionLocal() as db:
        db.execute(select(func.pg_advisory_xact_lock(_lock_key(env, service))))

        ticket = arca_ticket_crud.get(db, env, service)
        if ticket and _is_usable(ticket.expiration_time):
            return _as_dict(service, ticket.token, ticket.sign, ticket.expiration_time)

        adopted = _adopt_legacy_ticket(db, env, service)
        if adopted:
            db.commit()
            return adopted

        fresh = arca_query(service)
        arca_ticket_crud.save(
            db,
            env=env,
            service=service,
            token=fresh["token"],
            sign=fresh["sign"],
            expiration_time=datetime.fromisoformat(fresh["expiration_time"]),
        )
        db.commit()
        return fresh
