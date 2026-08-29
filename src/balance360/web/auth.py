"""Las pantallas sin sesión: ingresar, crear cuenta y recuperar la contraseña.

Es el único módulo de `web/` que se monta **sin** `Depends(get_current_user)`, y no puede ser
de otra manera: son las puertas que se usan justamente cuando no hay sesión.

Tres cuidados que atraviesan todo el archivo:

**Ninguna pantalla dice si una dirección tiene cuenta.** Ni el login, ni el registro, ni el
"olvidé mi contraseña". Un mensaje distinto para "ese mail no existe" convierte cualquiera de
los tres formularios en la lista de quién usa Balance360. Lo que sí puede contar qué pasó es
el mail que llega a esa casilla, porque ahí ya está el dueño.

**Los errores se atrapan acá**, contra la convención del proyecto de dejarlos subir al handler
global. El handler contesta un `<h1>No se pudo completar la operación</h1>` pelado, que en una
pantalla de login es una pared: el usuario no tiene dónde volver a intentar. Acá se vuelve a
dibujar el formulario con lo que escribió y el motivo arriba.

**La lógica no está en las rutas.** Estas funciones leen un `Form`, llaman a
`services/registration.py` o a `services/password_reset.py` y eligen qué template dibujar.
"""

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from balance360.crud import user as user_crud
from balance360.dependencies import get_db
from balance360.exceptions import Balance360Error
from balance360.services import password_reset as reset_service
from balance360.services import registration
from balance360.services.auth import create_access_token
from balance360.services.security import PASSWORD_MIN_LENGTH
from balance360.web.templating import templates

router = APIRouter(prefix="/login")

# El registro y la recuperación cuelgan de la raíz y no de `/login`: son de la cuenta y no del
# acto de entrar, y estas URLs terminan adentro de un mail, donde `/login/forgot-password` se
# leería como si hubiera que estar logueado para pedirlo.
public_router = APIRouter()

# Lo que la pantalla de registro necesita saber para no dejar escribir algo que la base va a
# rechazar después con un error que no explica nada.
_FORM_LIMITS: dict[str, object] = {
    "password_min_length": PASSWORD_MIN_LENGTH,
    "email_max_length": registration.EMAIL_MAX_LENGTH,
    "full_name_max_length": registration.FULL_NAME_MAX_LENGTH,
}


def _message(
    request: Request,
    title: str,
    message: str,
    link_href: str = "/login/",
    link_text: str = "Ir a ingresar",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="auth/message.html",
        context={
            "title": title,
            "message": message,
            "link_href": link_href,
            "link_text": link_text,
        },
        status_code=status_code,
    )


def _render(request: Request, name: str, context: dict[str, object]) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name=name, context=context)


@router.get("/", response_class=HTMLResponse)
def login_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="auth/login.html")


@router.post("/", response_class=RedirectResponse)
def login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
) -> Response:
    """Entrar.

    **El mismo mensaje para las dos formas de no entrar**: dirección que no existe y contraseña
    equivocada. La tercera —la cuenta existe, la contraseña es correcta y está apagada— sí dice
    qué pasa, y no es una inconsistencia: quien llegó hasta ahí ya demostró que la contraseña es
    suya, así que no queda nada que ocultarle. Al revés, "email o contraseña incorrectos" lo
    mandaría a cambiar una contraseña que está bien.

    Es el mismo criterio que ya usaba `services/api_token.py` con la cuenta desactivada.
    """
    user = user_crud.get_by_email(db, email)

    if not user or not user_crud.verify_user_password(user, password):
        return _render(
            request,
            "auth/login.html",
            {"error": "Email o contraseña incorrectos", "email": email},
        )

    if not user.is_active:
        return _render(
            request,
            "auth/login.html",
            {
                "error": (
                    "Tu cuenta todavía no está habilitada. Te avisamos por mail cuando lo esté."
                ),
                "email": email,
            },
        )

    token = create_access_token(user.id)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("access_token", token, httponly=True)

    return response


@router.post("/logout", response_class=RedirectResponse)
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login/", status_code=302)
    response.delete_cookie("access_token")

    return response


@public_router.get("/register", response_class=HTMLResponse)
def register_form(request: Request) -> HTMLResponse:
    return _render(request, "auth/register.html", dict(_FORM_LIMITS))


@public_router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
) -> HTMLResponse:
    """Crear la cuenta —apagada— y mandar el link de confirmación.

    **Termina siempre en la misma pantalla**, exista o no la dirección. Es la mitad de arriba
    del invariante; la de abajo es que el servicio manda un mail en las tres ramas.

    Las validaciones de largo están acá y no en el servicio porque son de la pantalla: `users`
    tiene columnas cortas (50 y 30) y el navegador ya las corta con `maxlength`, así que esto es
    la red de abajo para el que postea a mano. El mínimo de la contraseña, en cambio, es
    política y vive en `services/security.py`.
    """
    context = dict(_FORM_LIMITS) | {"full_name": full_name, "email": email}

    error = _check_registration_input(email, password, full_name)
    if error is not None:
        return _render(request, "auth/register.html", context | {"error": error})

    try:
        registration.register(db, email=email, password=password, full_name=full_name)
    except Balance360Error as failure:
        # Se pasó de intentos, o el mail no salió. Las dos cosas se le cuentan al que está
        # mirando: una pantalla que dice "listo" cuando el link nunca salió deja a alguien
        # esperando un mail que no existe.
        return _render(request, "auth/register.html", context | {"error": str(failure)})

    return _message(
        request,
        "Revisá tu casilla",
        f"Te mandamos un mail a {email.strip()} para confirmar la dirección.\n\n"
        "Si no llega en unos minutos, mirá el correo no deseado.",
    )


def _check_registration_input(email: str, password: str, full_name: str) -> str | None:
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"La contraseña necesita al menos {PASSWORD_MIN_LENGTH} caracteres."
    if len(email.strip()) > registration.EMAIL_MAX_LENGTH:
        return f"La dirección no puede pasar de {registration.EMAIL_MAX_LENGTH} caracteres."
    if len(full_name.strip()) > registration.FULL_NAME_MAX_LENGTH:
        return f"El nombre no puede pasar de {registration.FULL_NAME_MAX_LENGTH} caracteres."
    return None


@public_router.get("/confirm-email", response_class=HTMLResponse)
def confirm_email(
    request: Request, token: str = "", db: Session = Depends(get_db)
) -> HTMLResponse:
    """El link del mail.

    Es un GET que cambia estado, que en general sería un error: lo es porque del otro lado hay
    un click en un cliente de mail y no existe otra forma. Lo que sí se cuida es que sea de un
    solo uso y que **no abra sesión** — el token vivió 24 horas en una casilla.
    """
    user = registration.confirm(db, token) if token else None

    if user is None:
        return _message(
            request,
            "Ese link ya no sirve",
            "Puede haber vencido, o ya haberse usado. Creá la cuenta de nuevo con la misma "
            "dirección y te mandamos uno nuevo.",
            link_href="/register",
            link_text="Crear cuenta",
            status_code=400,
        )

    if user.is_active:
        # Una cuenta que ya estaba habilitada —creada a mano y confirmada después—: no tiene
        # ningún sentido decirle que espere.
        return _message(request, "Listo", "Confirmaste tu dirección. Ya podés entrar.")

    return _message(
        request,
        "Dirección confirmada",
        "Falta que habilitemos la cuenta. Te avisamos por mail cuando puedas entrar.",
    )


@public_router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="auth/forgot.html")


@public_router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password(
    request: Request, db: Session = Depends(get_db), email: str = Form(...)
) -> HTMLResponse:
    try:
        reset_service.request(db, email)
    except Balance360Error as failure:
        return _render(request, "auth/forgot.html", {"error": str(failure), "email": email})

    # El mismo texto haya cuenta o no. Es la razón por la que el servicio manda un mail también
    # cuando no encontró a nadie: si esa rama no pudiera fallar, el error de la otra sería la
    # respuesta que esta pantalla se cuida de no dar.
    return _message(
        request,
        "Revisá tu casilla",
        f"Si hay una cuenta con {email.strip()}, le mandamos un link para elegir una "
        "contraseña nueva. Vale una hora.",
    )


@public_router.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(
    request: Request, token: str = "", db: Session = Depends(get_db)
) -> HTMLResponse:
    """El formulario para elegir la contraseña nueva.

    Valida el token **antes** de dibujarlo, para no hacerle escribir una contraseña dos veces a
    alguien que va a recibir "este link no sirve" al final. No lo consume: abrir el mail no
    puede quemar el permiso.
    """
    user = reset_service.get_user_for_token(db, token) if token else None
    if user is None:
        return _expired_reset(request)

    return _render(
        request, "auth/reset.html", {"token": token, "email": user.email, **_FORM_LIMITS}
    )


@public_router.post("/reset-password", response_class=HTMLResponse)
def reset_password(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
) -> HTMLResponse:
    user = reset_service.get_user_for_token(db, token)
    if user is None:
        return _expired_reset(request)

    context: dict[str, object] = {"token": token, "email": user.email, **_FORM_LIMITS}

    if len(password) < PASSWORD_MIN_LENGTH:
        context["error"] = f"La contraseña necesita al menos {PASSWORD_MIN_LENGTH} caracteres."
        return _render(request, "auth/reset.html", context)
    if password != password_confirm:
        context["error"] = "Las dos contraseñas no coinciden."
        return _render(request, "auth/reset.html", context)

    if reset_service.consume(db, token, password) is None:
        # Se quemó entre el GET y el POST: dos pestañas, o el mismo link abierto dos veces.
        return _expired_reset(request)

    return _message(request, "Contraseña cambiada", "Ya podés entrar con la nueva.")


def _expired_reset(request: Request) -> HTMLResponse:
    return _message(
        request,
        "Ese link ya no sirve",
        "Los links de recuperación valen una hora y se usan una sola vez. Pedí uno nuevo.",
        link_href="/forgot-password",
        link_text="Pedir otro link",
        status_code=400,
    )
