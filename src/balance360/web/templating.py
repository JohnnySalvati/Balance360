from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.templating import Jinja2Templates

from balance360.models.money import money
from balance360.services.text import format_cuit

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def format_amount(value):
    us_format = f"{money(Decimal(str(value))):,.2f}"
    arg_format = us_format.translate(str.maketrans({",": ".", ".": ","}))
    return arg_format


templates.env.filters["amount"] = format_amount
templates.env.filters["currency"] = lambda v: f"$ {format_amount(v)}"
templates.env.filters["cuit"] = format_cuit

templates.env.globals["current_year"] = lambda: date.today().year
templates.env.globals["current_month"] = lambda: date.today().month
templates.env.globals["today"] = lambda: date.today().isoformat()
