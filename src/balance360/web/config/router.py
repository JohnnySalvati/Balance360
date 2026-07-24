from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from balance360.web.config import (
    accounts,
    app_config,
    categories,
    contacts,
    currencies,
    entities,
    exchange_rates,
    fiscal_identity,
    products,
    users,
)
from balance360.web.templating import templates

router = APIRouter(prefix="/config")

router.include_router(accounts.router)
router.include_router(app_config.router)
router.include_router(categories.router)
router.include_router(contacts.router)
router.include_router(currencies.router)
router.include_router(entities.router)
router.include_router(exchange_rates.router)
router.include_router(fiscal_identity.router)
router.include_router(products.router)
router.include_router(users.router)


@router.get("/", response_class=HTMLResponse)
def config_index(request: Request):
    return templates.TemplateResponse(request=request, name="config/index.html", context={})
