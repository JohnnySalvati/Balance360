"""Armado y envio del mail con el comprobante.

No sale a la red: se reemplaza smtplib.SMTP_SSL por un doble que se queda con el
EmailMessage. Lo que se prueba es lo que decide el codigo —quien va en el sobre,
como queda el adjunto, que error sale cuando falta configuracion— y no que
smtplib funcione, que eso ya esta probado.
"""

import smtplib
from types import SimpleNamespace

import pytest

from balance360.exceptions import EmailError
from balance360.schemas.entity import EntityCreate
from balance360.services import email as email_service
from balance360.services.invoice_pdf import pdf_filename
from balance360.web.invoices import _sender_display_name, _split_addresses
from tests import factories


class FakeSMTP:
    """Doble de smtplib.SMTP_SSL. Guarda lo enviado para poder inspeccionarlo."""

    sent: list[tuple[object, list[str]]] = []
    logins: list[tuple[str, str]] = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        FakeSMTP.logins.append((user, password))

    def send_message(self, message, to_addrs=None):
        FakeSMTP.sent.append((message, to_addrs))


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent = []
    FakeSMTP.logins = []
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(
        email_service,
        "settings",
        SimpleNamespace(
            smtp_configured=True,
            smtp_host="smtppro.zoho.com",
            smtp_port=465,
            smtp_user="miguelsalvati@insoft.net.ar",
            smtp_password="secreta",
            smtp_from="miguelsalvati@insoft.net.ar",
        ),
    )
    return FakeSMTP


def test_send_email_basico(smtp):
    email_service.send_email(to=["cliente@ejemplo.com"], subject="Asunto", body="Cuerpo")

    message, envelope = smtp.sent[0]
    assert message["To"] == "cliente@ejemplo.com"
    assert message["Subject"] == "Asunto"
    assert message["From"] == "miguelsalvati@insoft.net.ar"
    assert envelope == ["cliente@ejemplo.com"]
    assert smtp.logins == [("miguelsalvati@insoft.net.ar", "secreta")]


def test_cc_va_en_el_sobre_ademas_de_la_cabecera(smtp):
    """El bug clasico: el Cc figura en el header y el servidor no se lo manda a
    nadie, porque el sobre SMTP se arma aparte."""
    email_service.send_email(
        to=["cliente@ejemplo.com"],
        cc=["contador@ejemplo.com"],
        subject="Asunto",
        body="Cuerpo",
    )

    message, envelope = smtp.sent[0]
    assert message["Cc"] == "contador@ejemplo.com"
    assert envelope == ["cliente@ejemplo.com", "contador@ejemplo.com"]


def test_adjunto_pdf(smtp):
    email_service.send_email(
        to=["cliente@ejemplo.com"],
        subject="Asunto",
        body="Cuerpo",
        attachments=[("A-00005-00000123.pdf", b"%PDF-1.7 fake", "pdf")],
    )

    message, _ = smtp.sent[0]
    adjuntos = [p for p in message.iter_attachments()]
    assert len(adjuntos) == 1
    assert adjuntos[0].get_filename() == "A-00005-00000123.pdf"
    assert adjuntos[0].get_content_type() == "application/pdf"
    assert adjuntos[0].get_payload(decode=True) == b"%PDF-1.7 fake"


def test_reply_to_y_from_display(smtp):
    """La entidad emisora cambia el remitente visible, no la casilla autenticada."""
    email_service.send_email(
        to=["cliente@ejemplo.com"],
        subject="Asunto",
        body="Cuerpo",
        from_display="InSoft",
        reply_to="ventas@insoft.net.ar",
    )

    message, _ = smtp.sent[0]
    assert message["From"] == "InSoft <miguelsalvati@insoft.net.ar>"
    assert message["Reply-To"] == "ventas@insoft.net.ar"


def test_sin_configuracion_smtp_da_error_de_dominio(monkeypatch):
    monkeypatch.setattr(email_service, "settings", SimpleNamespace(smtp_configured=False))
    with pytest.raises(EmailError, match="no esta configurado"):
        email_service.send_email(to=["a@b.com"], subject="x", body="y")


def test_sin_destinatario_da_error_de_dominio(smtp):
    with pytest.raises(EmailError, match="destinatario"):
        email_service.send_email(to=[""], subject="x", body="y")


def test_credenciales_rechazadas_se_traducen(smtp, monkeypatch):
    def login_que_falla(self, user, password):
        raise smtplib.SMTPAuthenticationError(535, b"auth failed")

    monkeypatch.setattr(FakeSMTP, "login", login_que_falla)
    with pytest.raises(EmailError, match="app password"):
        email_service.send_email(to=["a@b.com"], subject="x", body="y")


@pytest.mark.parametrize(
    "raw, esperado",
    [
        ("", []),
        ("a@b.com", ["a@b.com"]),
        ("a@b.com, c@d.com", ["a@b.com", "c@d.com"]),
        ("  a@b.com ,, c@d.com  ", ["a@b.com", "c@d.com"]),
    ],
)
def test_split_addresses(raw, esperado):
    assert _split_addresses(raw) == esperado


def test_pdf_filename_usa_letra_pos_y_numero():
    invoice = SimpleNamespace(voucher_type=SimpleNamespace(value="A"), pos=5, number=123)
    assert pdf_filename(invoice) == "A-00005-00000123.pdf"


# --- Identidad de mail por entidad -------------------------------------------


def test_el_nombre_del_remitente_cae_al_nombre_de_la_entidad(db):
    """Sin configurar nada, la entidad ya se presenta con su nombre."""
    entity = factories.make_entity(db, name="InSoft")

    assert _sender_display_name(entity) == "InSoft"


def test_el_nombre_configurado_gana(db):
    entity = factories.make_entity(db, name="InSoft")
    entity.email_display_name = "InSoft — Facturación"
    db.commit()

    assert _sender_display_name(entity) == "InSoft — Facturación"


def test_la_direccion_de_la_entidad_va_en_reply_to_y_no_en_from(smtp):
    """Un From ajeno a la casilla autenticada no valida SPF/DKIM.

    Por eso la identidad de la entidad viaja en Reply-To: el destinatario le
    contesta a la entidad, pero el mail sale —y se autentica— desde la casilla
    configurada en el servidor.
    """
    email_service.send_email(
        to=["cliente@ejemplo.com"],
        subject="Asunto",
        body="Cuerpo",
        from_display="Familia",
        reply_to="familia@ejemplo.com",
    )

    message, _ = smtp.sent[0]
    assert message["From"] == "Familia <miguelsalvati@insoft.net.ar>"
    assert message["Reply-To"] == "familia@ejemplo.com"


def test_los_campos_vacios_del_form_se_guardan_como_none():
    """Un input de texto vacio llega como "", no como None."""
    data = EntityCreate(
        name="InSoft",
        email_display_name="",
        email_reply_to="   ",
        email_signature="",
    )

    assert data.email_display_name is None
    assert data.email_reply_to is None
    assert data.email_signature is None


def test_se_limpian_los_espacios_de_los_bordes():
    data = EntityCreate(name="InSoft", email_reply_to="  ventas@ejemplo.com  ")

    assert data.email_reply_to == "ventas@ejemplo.com"
