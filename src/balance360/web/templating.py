from datetime import date
from pathlib import Path
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

def format_amount(value):
    return f"{value:,.2f}"

templates.env.filters["amount"] = format_amount
templates.env.filters["currency"] = lambda v: f"$ {v:,.2f}"
templates.env.globals["current_year"] = lambda: date.today().year
