from fastapi import FastAPI
from balance360.models import user, entity, account, currency, contact, category, transaction, import_rule, attachment  # noqa: F401
from balance360.routers import category, currency, contact, account, entity, user, transaction, exchange_rate, import_rule
from balance360.web import router as web_router
from balance360.web import reports_router
from balance360.web import config_router

app = FastAPI(title="Balance360")

app.include_router(category.router, prefix="/api")
app.include_router(currency.router, prefix="/api")
app.include_router(contact.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(entity.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(transaction.router, prefix="/api")
app.include_router(exchange_rate.router, prefix="/api")
app.include_router(import_rule.router, prefix="/api")
app.include_router(web_router.router)
app.include_router(reports_router.router)
app.include_router(config_router.router)
