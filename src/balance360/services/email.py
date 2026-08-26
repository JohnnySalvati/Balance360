"""Envio de mails por SMTP.

Transporte puro: no sabe que es un comprobante ni una factura. Recibe
destinatarios, texto y adjuntos ya armados, y los entrega. La decision de que
mandar vive en la capa web; aca solo esta el como.

El nombre del modulo convive con el paquete `email` de la biblioteca estandar
sin pisarlo: desde Python 3 los imports son absolutos, asi que el
`from email.message import EmailMessage` de abajo resuelve a la stdlib y no a
este archivo.
"""

import smtplib
from email.message import EmailMessage

from balance360.database import settings
from balance360.exceptions import EmailError

# (nombre_de_archivo, contenido, subtipo_mime). Solo se adjuntan PDFs por ahora,
# asi que el tipo principal "application" queda fijo en add_attachment.
Attachment = tuple[str, bytes, str]


def send_email(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    attachments: list[Attachment] | None = None,
    from_display: str | None = None,
    reply_to: str | None = None,
) -> None:
    """Envia un mail. Lanza EmailError si no se puede.

    `from_display` y `reply_to` estan previstos para cuando mas de una entidad
    emita comprobantes: el transporte SMTP sigue siendo uno solo (una casilla
    autenticada, que es lo que sostiene SPF y DKIM) y lo unico que cambia es el
    remitente visible. Poner una direccion ajena en From haria que el mail no
    valide; por eso la identidad de la entidad va en Reply-To.
    """
    if not settings.smtp_configured:
        raise EmailError(
            "El envio de mails no esta configurado: faltan las variables SMTP_* en el .env"
        )

    recipients = [address for address in to if address]
    if not recipients:
        raise EmailError("No hay destinatario para el mail")

    cc = [address for address in (cc or []) if address]

    message = EmailMessage()
    # mypy: smtp_from y smtp_user son str|None en Settings, pero smtp_configured
    # ya garantizo que no son None.
    sender = str(settings.smtp_from)
    message["From"] = f"{from_display} <{sender}>" if from_display else sender
    message["To"] = ", ".join(recipients)
    if cc:
        message["Cc"] = ", ".join(cc)
    if reply_to:
        message["Reply-To"] = reply_to
    message["Subject"] = subject
    message.set_content(body)

    for filename, content, subtype in attachments or []:
        message.add_attachment(content, maintype="application", subtype=subtype, filename=filename)

    # Cc viaja en la cabecera, pero el sobre SMTP necesita la lista completa: un
    # destinatario que no este aca no recibe nada aunque figure en el header.
    envelope = recipients + cc

    try:
        with smtplib.SMTP_SSL(str(settings.smtp_host), settings.smtp_port, timeout=30) as smtp:
            smtp.login(str(settings.smtp_user), str(settings.smtp_password))
            smtp.send_message(message, to_addrs=envelope)
    except smtplib.SMTPAuthenticationError as e:
        raise EmailError(
            "El servidor SMTP rechazo las credenciales. Con 2FA hay que usar una "
            "app password, no la contrasenia de la cuenta."
        ) from e
    except (smtplib.SMTPException, OSError) as e:
        # OSError cubre el socket: host mal escrito, puerto cerrado, timeout.
        raise EmailError(f"No se pudo enviar el mail: {e}") from e
