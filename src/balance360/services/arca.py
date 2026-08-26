import base64
import json
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key, pkcs7
from cryptography.x509 import load_pem_x509_certificate
from cryptography.x509.oid import NameOID
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.poolmanager import PoolManager
from zeep import Client
from zeep.cache import SqliteCache
from zeep.exceptions import Fault
from zeep.transports import Transport

from balance360.database import settings
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


class TicketManager:
    def __init__(self) -> None:
        self.tickets: dict = self.read_file()

    def save_new_ticket(self, service: str, token: str, sign: str, expiration_time: str):
        self.tickets[f"{settings.afip_env}:{service}"] = {
            "service": service,
            "token": token,
            "sign": sign,
            "expiration_time": expiration_time,
        }
        with open("ticket_arca.json", "w", encoding="utf-8") as file:
            json.dump(self.tickets, file, indent=4, ensure_ascii=False)

    def get_valid_ticket(self, service: str) -> dict | None:
        ticket = self.tickets.get(f"{settings.afip_env}:{service}")
        if ticket:
            if datetime.fromisoformat(ticket["expiration_time"]) > datetime.now(
                timezone.utc
            ) + timedelta(minutes=5):
                return ticket

    def read_file(self) -> dict:
        try:
            with open("ticket_arca.json", "r", encoding="utf-8") as file:
                return json.load(file)

        except (FileNotFoundError, json.JSONDecodeError):
            return {}


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
    tiket_manager = TicketManager()
    ticket = tiket_manager.get_valid_ticket(service)
    if not ticket:
        ticket = arca_query(service)
        tiket_manager.save_new_ticket(**ticket)
    return ticket
