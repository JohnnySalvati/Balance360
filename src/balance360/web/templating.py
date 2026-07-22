from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates

from balance360.services.text import format_cuit

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def format_amount(value):
    return f"{value:,.2f}"


templates.env.filters["amount"] = format_amount
templates.env.filters["currency"] = lambda v: f"$ {v:,.2f}"
templates.env.filters["cuit"] = format_cuit

templates.env.globals["current_year"] = lambda: date.today().year
templates.env.globals["current_month"] = lambda: date.today().month
