import base64, json
import xml.etree.ElementTree as ET
from zeep import Client
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7, load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from balance360.database import settings

WSAA_URL = {
    "homo": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL",
    "prod": "https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL"
}

class TicketManager:
    def __init__(self) -> None:
        self.tickets: dict = self.read_file()

    def save_new_ticket(self, service: str, token: str, sign: str, expiration_time: datetime):
        self.tickets[service] = {
            "service": service,
            "token": token,
            "sign": sign,
            "expiration_time": expiration_time
        }
        with open('ticket_arca.json', 'w', encoding='utf-8') as file:
            json.dump(self.tickets, file, indent=4, ensure_ascii=False)

    def get_valid_ticket(self, service: str) -> dict|None:
        ticket = self.tickets.get(service)
        if ticket:
            if datetime.fromisoformat(ticket["expiration_time"]) > datetime.now(timezone.utc) + timedelta(minutes=5):
                return self.tickets[service]
        
    def read_file(self) -> dict:
        try:
            with open('ticket_arca.json', 'r', encoding='utf-8') as file:
                return json.load(file)
        
        except (FileNotFoundError, json.JSONDecodeError):
             return {}

def build_tra(service: str) ->str:
    timestamp=int(datetime.now().timestamp())
    generation_time=datetime.now(timezone.utc).isoformat()
    expiration_time=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

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

def sign(xml: str) ->bytes:

    private_key_path = settings.private_key_path
    cert_path = settings.cert_path
    
    if not cert_path or not private_key_path:
        raise ValueError("Certificados de ARCA no configurados")

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

def parse_xml(response: str, service: str) -> dict:
    tree = ET.fromstring(response)
    token = tree.findtext(".//token")
    sign = tree.findtext(".//sign")
    expiration_time = tree.findtext(".//expirationTime")
    return {
        "service": service,
        "token": token,
        "sign": sign,
        "expiration_time": expiration_time
    }

def arca_query(service: str) -> dict:
    
    xml = build_tra(service)

    xml_signed = sign(xml)

    client = Client(WSAA_URL[settings.afip_env])
    response = client.service.loginCms(in0=base64.b64encode(xml_signed).decode("utf-8"))

    return parse_xml(response, service)

def get_access_ticket(service: str) -> dict:
    tiket_manager = TicketManager()
    ticket = tiket_manager.get_valid_ticket(service)
    if not ticket:
        ticket = arca_query(service)
        tiket_manager.save_new_ticket(**ticket)
    return ticket
