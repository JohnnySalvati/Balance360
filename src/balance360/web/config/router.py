from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from balance360.web.config import exchange_rates, categories, accounts, entities, contacts, products, currencies, users, app_config

router = APIRouter(prefix="/config")
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

router.include_router(exchange_rates.router)
router.include_router(categories.router)
router.include_router(accounts.router)
router.include_router(entities.router)
router.include_router(contacts.router)
router.include_router(products.router)
router.include_router(currencies.router)
router.include_router(users.router)
router.include_router(app_config.router)

@router.get("/", response_class=HTMLResponse)
def config_index(request: Request):
    return templates.TemplateResponse(request=request, name="config/index.html", context={})
