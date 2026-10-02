from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.templating import Jinja2Templates

from balance360.models.money import money
from balance360.services.text import format_cuit

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
STATIC_DIR = Path(__file__).parent.parent / "static"

templates = Jinja2Templates(directory=TEMPLATES_DIR)


def format_amount(value):
    us_format = f"{money(Decimal(str(value))):,.2f}"
    arg_format = us_format.translate(str.maketrans({",": ".", ".": ","}))
    return arg_format


templates.env.filters["amount"] = format_amount
templates.env.filters["currency"] = lambda v: f"$ {format_amount(v)}"


def format_date(value):
    """Fecha en dd/mm/aaaa, que es como se lee y se escribe acá.

    Una `date` se imprime sola en ISO (2026-04-07) y eso en estas pantallas se lee al
    revés. El filtro existe para que el formato sea una decisión en un solo lugar y no
    dependa de que cada template se acuerde del strftime.
    """
    return value.strftime("%d/%m/%Y") if value else ""


templates.env.filters["cuit"] = format_cuit
templates.env.filters["date"] = format_date

templates.env.globals["current_year"] = lambda: date.today().year
templates.env.globals["current_month"] = lambda: date.today().month
templates.env.globals["today"] = lambda: date.today().isoformat()


def static_url(path: str) -> str:
    """La URL de un archivo de /static con la fecha del archivo pegada detrás.

    El HTML se pide en cada navegación, pero un .js ya cacheado no: el navegador lo
    sirve de su copia y un cambio de código no llega nunca —se ve el markup nuevo
    corriendo el script viejo, que es un síntoma imposible de diagnosticar desde
    adentro—. El sufijo cambia solo cuando cambia el archivo, así que la cache sigue
    valiendo mientras el contenido sea el mismo.

    Si el archivo no está (un nombre mal escrito), devuelve la URL pelada: que falte
    el cache-busting es un problema menor al lado de romper el render de la página.
    """
    url = f"/static/{path}"
    try:
        return f"{url}?v={int((STATIC_DIR / path).stat().st_mtime)}"
    except OSError:
        return url


templates.env.globals["static_url"] = static_url
