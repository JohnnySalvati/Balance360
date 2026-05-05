from fastapi import FastAPI
from balance360.models import user, entity, account, currency, contact, category, transaction, attachment  # noqa: F401
from balance360.routers import category, currency, contact, account, entity, user, transaction, exchange_rate

app = FastAPI(title="Balance360")

app.include_router(category.router)
app.include_router(currency.router)
app.include_router(contact.router)
app.include_router(account.router)
app.include_router(entity.router)
app.include_router(user.router)
app.include_router(transaction.router)
app.include_router(exchange_rate.router)

