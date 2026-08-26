"""Consulta al padron de ARCA (ws_sr_padron_a5) para completar un contacto.

Trae razon social, domicilio fiscal y condicion frente al IVA a partir del CUIT,
para no tipearlos a mano ni equivocarse. La firma del servicio y la forma de la
respuesta estan tomadas del WSDL:

    getPersona_v2(token, sign, cuitRepresentada, idPersona) -> personaReturn
    personaReturn(datosGenerales, datosRegimenGeneral, datosMonotributo, error*)

`cuitRepresentada` es el duenio del certificado (ver arca.get_certificate_cuit) y
`idPersona` el CUIT que se consulta.

El ticket se pide para ws_sr_constancia_inscripcion y no para ws_sr_padron_a5:
ARCA saco el A5 del Administrador de Relaciones, y "Consulta de constancia de
inscripcion" es el que lo reemplaza. Comparten el endpoint personaServiceA5 y
la forma de la respuesta.

Se eligio este y no el A13 —que tambien figura en el listado— porque el A13
devuelve razon social y domicilio pero NO los impuestos ni el monotributo, o sea
que no permite deducir la condicion frente al IVA.

El servicio necesita estar delegado al certificado en el portal de ARCA; sin eso
WSAA responde "Computador no autorizado a acceder al servicio" y no se llega ni
a la consulta. En produccion se delega por Administrador de Relaciones; en
homologacion por WSASS, donde figura como ws_sr_constancia_inscripcion (la lista
se ordena por codigo, no por descripcion).

El padron de homologacion tiene contribuyentes de prueba, no los reales, pero
alcanza para probar la cadena entera. Estos tres existen y cubren una condicion
IVA cada uno:

    30500010912 -> INSCRIPTO
    20000000001 -> MONOTRIBUTO
    33693450239 -> FINAL

Un CUIT sin datos se manifiesta de dos formas distintas y las dos terminan en
PadronError: un Fault ("No existe persona con ese Id") o una respuesta con
datosGenerales vacio.
"""

from dataclasses import dataclass
from typing import Any

from requests.exceptions import RequestException
from zeep.exceptions import Fault

from balance360.database import settings
from balance360.enums import CondicionIva
from balance360.exceptions import ArcaError, PadronError
from balance360.services.arca import build_client, get_access_ticket, get_certificate_cuit
from balance360.services.text import digits_only

SERVICE = "ws_sr_constancia_inscripcion"

WSDL_URL = {
    "homo": "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl",
    "prod": "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl",
}

# idImpuesto del padron. El monotributo no figura como impuesto: viene en su
# propio bloque datosMonotributo, asi que se pregunta por ese antes que por estos.
IVA_INSCRIPTO = 30
IVA_EXENTO = 32

# El domicilio va a Contact.address, que es String(200).
ADDRESS_MAX_LENGTH = 200


@dataclass
class Taxpayer:
    tax_id: str
    name: str
    address: str | None
    condicion_iva: CondicionIva
    active: bool


def get_taxpayer(tax_id: str) -> Taxpayer:
    cuit = digits_only(tax_id)
    if len(cuit) != 11:
        raise PadronError("El CUIT tiene que tener 11 digitos")

    ticket = get_access_ticket(SERVICE)

    try:
        client = build_client(WSDL_URL[settings.afip_env])
        response = client.service.getPersona_v2(
            token=ticket["token"],
            sign=ticket["sign"],
            cuitRepresentada=int(get_certificate_cuit()),
            idPersona=int(cuit),
        )
    except Fault as e:
        raise PadronError(f"ARCA: {e}") from e
    except RequestException as e:
        raise ArcaError("No se puede conectar con ARCA, reintenta en unos minutos") from e

    return to_taxpayer(cuit, response)


def to_taxpayer(cuit: str, response: Any) -> Taxpayer:
    general = getattr(response, "datosGenerales", None)
    if general is None:
        raise PadronError(f"ARCA no tiene datos para el CUIT {cuit}")

    return Taxpayer(
        tax_id=cuit,
        name=_name(general),
        address=_address(getattr(general, "domicilioFiscal", None)),
        condicion_iva=_condicion_iva(response),
        active=str(getattr(general, "estadoClave", "") or "").upper() == "ACTIVO",
    )


def _name(general: Any) -> str:
    """Razon social para una persona juridica; nombre y apellido para una fisica."""
    razon_social = (getattr(general, "razonSocial", None) or "").strip()
    if razon_social:
        return razon_social

    nombre = (getattr(general, "nombre", None) or "").strip()
    apellido = (getattr(general, "apellido", None) or "").strip()
    return " ".join(part for part in (nombre, apellido) if part)


def _address(domicilio: Any) -> str | None:
    """Una sola linea, que es como la guarda Contact.address.

    Se omite la provincia cuando repite la localidad (CABA la trae dos veces) y
    se recorta al largo de la columna: preferimos un domicilio incompleto a que
    el alta explote al guardar.
    """
    if domicilio is None:
        return None

    parts: list[str] = []
    for field in ("direccion", "localidad", "descripcionProvincia"):
        value = (getattr(domicilio, field, None) or "").strip()
        if value and value.lower() not in (p.lower() for p in parts):
            parts.append(value)

    cod_postal = (getattr(domicilio, "codPostal", None) or "").strip()
    if cod_postal:
        parts.append(f"CP {cod_postal}")

    return ", ".join(parts)[:ADDRESS_MAX_LENGTH] or None


def _condicion_iva(response: Any) -> CondicionIva:
    if getattr(response, "datosMonotributo", None) is not None:
        return CondicionIva.MONOTRIBUTO

    regimen_general = getattr(response, "datosRegimenGeneral", None)
    impuestos = {
        impuesto.idImpuesto for impuesto in (getattr(regimen_general, "impuesto", None) or [])
    }

    if IVA_INSCRIPTO in impuestos:
        return CondicionIva.INSCRIPTO
    if IVA_EXENTO in impuestos:
        return CondicionIva.EXENTO
    return CondicionIva.FINAL
