from fastapi import APIRouter
from balance360.web import transactions, reports, import_rules, invoices
from balance360.web.config import router as config_router

router = APIRouter()
router.include_router(transactions.router)
router.include_router(reports.router)
router.include_router(config_router.router)
router.include_router(import_rules.router)
router.include_router(invoices.router)
