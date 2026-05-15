from pathlib import Path
from balance360.web import import_rules
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from balance360.web.config import exchange_rates, categories, accounts, entities, contacts

router = APIRouter(prefix="/config")
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

router.include_router(exchange_rates.router)
router.include_router(categories.router)
router.include_router(accounts.router)
router.include_router(entities.router)
router.include_router(contacts.router)

@router.get("/", response_class=HTMLResponse)
def config_index(request: Request):
    return templates.TemplateResponse(request=request, name="config/index.html", context={})
