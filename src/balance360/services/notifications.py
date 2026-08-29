"""Qué dice cada mail de la app, y cuál se puede perder sin consecuencias.

Separado de `services/email.py` porque los dos cambian por motivos distintos: cambiar de
proveedor SMTP no toca una palabra de estos textos, y corregir la redacción de un mail no
debería obligar a leer código de sockets.

**Importa el módulo `email`, no la función `send_email`.** Así el nombre se resuelve en cada
llamada y un test puede parchear el transporte en un solo lugar; con `from ... import
send_email` el parche no llegaría nunca.

La división que importa acá es otra: **cuáles se mandan sincrónicos y cuáles best effort.**
El link de confirmación y el de reset son el producto de la operación —si no salen, el usuario
se queda esperando un mail que no existe y hay que decírselo—. El aviso al operador y el "tu
contraseña cambió" acompañan a algo que ya ocurrió: hacerlos fallar sería deshacer un alta o
un cambio de contraseña por un problema de correo.
"""

import logging

from balance360.database import settings
from balance360.exceptions import EmailError
from balance360.services import email

logger = logging.getLogger(__name__)


def _link(path: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}{path}"


def _send_best_effort(to: list[str], subject: str, body: str) -> None:
    """Manda y, si no se puede, lo deja en el log. **No levanta.**

    Es para los mails que acompañan a una operación terminada. Un WARNING y no un ERROR: no
    hay nada roto que arreglar en la app, y el que lo lee necesita saber que ese aviso no
    llegó, no que se caiga algo.
    """
    try:
        email.send_email(to=to, subject=subject, body=body)
    except EmailError as error:
        logger.warning("No se pudo mandar el mail «%s» a %s: %s", subject, ", ".join(to), error)


def send_confirmation(to: str, full_name: str, token: str) -> None:
    """El link que prueba que la casilla es suya. Sincrónico: es el producto del registro."""
    email.send_email(
        to=[to],
        subject="Confirmá tu dirección en Balance360",
        body=(
            f"Hola {full_name},\n\n"
            "Alguien creó una cuenta de Balance360 con esta dirección. Para confirmarla, "
            "entrá acá:\n\n"
            f"{_link(f'/confirm-email?token={token}')}\n\n"
            "El link vale 24 horas. Después de confirmar, la cuenta queda a la espera de que "
            "la habilitemos: te avisamos por mail cuando puedas entrar.\n\n"
            "Si no fuiste vos, no hagas nada: sin ese click la cuenta no se usa.\n"
        ),
    )


def send_password_reset(to: str, full_name: str, token: str) -> None:
    """El link para elegir una contraseña nueva. Sincrónico, por lo mismo que el de arriba."""
    email.send_email(
        to=[to],
        subject="Recuperar tu contraseña de Balance360",
        body=(
            f"Hola {full_name},\n\n"
            "Pediste recuperar tu contraseña de Balance360. Elegí una nueva acá:\n\n"
            f"{_link(f'/reset-password?token={token}')}\n\n"
            "El link vale una hora y se usa una sola vez.\n\n"
            "Si no lo pediste vos, ignorá este mail: tu contraseña sigue siendo la de "
            "siempre mientras nadie abra ese link.\n"
        ),
    )


def send_password_reset_unknown(to: str) -> None:
    """La otra rama del "olvidé mi contraseña": esa dirección no tiene cuenta.

    Existe para que las dos ramas hagan lo mismo. Si esta no mandara nada, sería la única que
    no puede fallar por un problema de SMTP, y el error pasaría a significar "esa dirección
    tiene cuenta acá" — justo lo que la pantalla se cuida de no contestar.

    **No dice "no existe".** El texto habla de "no encontramos una cuenta", que es lo mismo
    para el que se equivocó de dirección y no delata nada de la que sí existe.
    """
    email.send_email(
        to=[to],
        subject="Recuperar tu contraseña de Balance360",
        body=(
            "Alguien pidió recuperar una contraseña de Balance360 con esta dirección, pero "
            "no encontramos ninguna cuenta asociada.\n\n"
            "Si tenés cuenta, puede que sea con otra dirección. Si no fuiste vos, ignorá "
            "este mail.\n"
        ),
    )


def send_account_exists(to: str, full_name: str) -> None:
    """"Ya tenés cuenta acá". Best effort.

    Es la tercera rama del registro y el único mail que cuenta qué pasó de verdad — y llega a
    la casilla del dueño de la cuenta, que es quien tiene derecho a saberlo. La pantalla, en
    las tres ramas, dice lo mismo.
    """
    _send_best_effort(
        to=[to],
        subject="Ya tenés una cuenta en Balance360",
        body=(
            f"Hola {full_name},\n\n"
            "Alguien intentó crear una cuenta de Balance360 con esta dirección, que ya tiene "
            "una.\n\n"
            "Si fuiste vos y no te acordás la contraseña, pedí una nueva desde "
            "«Olvidé mi contraseña» en la pantalla de ingreso.\n"
        ),
    )


def send_password_changed(to: str, full_name: str) -> None:
    """El aviso de que la contraseña cambió. Best effort, y sale igual.

    Es la única señal que le llega al dueño de la casilla si el reset lo pidió otro — y llega
    a un lugar al que ese otro ya no puede volver, porque el link se consumió.
    """
    _send_best_effort(
        to=[to],
        subject="Tu contraseña de Balance360 cambió",
        body=(
            f"Hola {full_name},\n\n"
            "Tu contraseña de Balance360 se cambió recién.\n\n"
            "Si fuiste vos, no hay nada que hacer. Si no, escribinos: alguien con acceso a "
            "esta casilla entró a tu cuenta.\n"
        ),
    )


def send_account_activated(to: str, full_name: str) -> None:
    """"Ya podés entrar". Best effort: la cuenta quedó habilitada igual.

    Sin esto, el que se registró no tiene forma de enterarse de que le abrieron la puerta —
    la única señal sería volver a probar el login cada tanto.
    """
    _send_best_effort(
        to=[to],
        subject="Tu cuenta de Balance360 está habilitada",
        body=(
            f"Hola {full_name},\n\n"
            f"Ya podés entrar a Balance360 con tu dirección y tu contraseña:\n\n"
            f"{_link('/login/')}\n"
        ),
    )


def notify_operator_registration(email_address: str, full_name: str) -> None:
    """Que alguien se registró. Best effort, y a `OPERATOR_EMAIL`.

    Avisa de una cuenta que **todavía no se puede usar**: falta que confirme la dirección y
    falta habilitarla. Eso es a propósito —el que se registró y quedó a mitad de camino
    también es información— y el cuerpo lo dice con todas las letras para que nadie lea
    "usuario nuevo" donde dice "alguien se anotó".

    Sin la variable queda un INFO en el log, no un WARNING: no hay nada roto ni nadie
    esperando. La línea nombra la variable, que es lo único que hace falta para prenderlo.
    """
    if not settings.operator_email:
        logger.info(
            "Alta nueva de %s (%s). Sin OPERATOR_EMAIL no se avisa por mail.",
            email_address,
            full_name,
        )
        return

    _send_best_effort(
        to=[settings.operator_email],
        subject="Balance360: alguien se registró",
        body=(
            f"{full_name} <{email_address}> creó una cuenta en Balance360.\n\n"
            "Todavía no puede entrar: la cuenta nace apagada. Cuando confirme la dirección, "
            "habilitala desde Configuración → Usuarios y le llega el aviso.\n"
        ),
    )
