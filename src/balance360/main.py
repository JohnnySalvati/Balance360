from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi import Request as FastAPIRequest
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from balance360.dependencies import get_current_user
from balance360.models import (  # noqa: F401
    account,
    attachment,
    category,
    contact,
    currency,
    entity,
    import_rule,
    transaction,
    user,
)
from balance360.routers import (
    account,
    category,
    contact,
    currency,
    entity,
    exchange_rate,
    import_rule,
    transaction,
    user,
)
from balance360.web import auth
from balance360.web import router as web_router

app = FastAPI(title="Balance360")

static_files = StaticFiles(directory=Path(__file__).parent / "static")

app.mount(path="/static", app=static_files, name="static")

app.include_router(category.router, prefix="/api")
app.include_router(currency.router, prefix="/api")
app.include_router(contact.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(entity.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(transaction.router, prefix="/api")
app.include_router(exchange_rate.router, prefix="/api")
app.include_router(import_rule.router, prefix="/api")
app.include_router(web_router.router, dependencies=[Depends(get_current_user)])
app.include_router(auth.router)


@app.exception_handler(401)
async def unauthorized_handler(request: FastAPIRequest, exc):
    return RedirectResponse(url="/login/")
