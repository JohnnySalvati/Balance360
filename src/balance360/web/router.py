from fastapi import APIRouter
from balance360.web import transactions

router = APIRouter()
router.include_router(transactions.router)
