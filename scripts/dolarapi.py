from sqlalchemy.orm import Session
from balance360.services.rate_sync import sync_uva
from balance360.dependencies import SessionLocal


with SessionLocal() as db:
    print(sync_uva(db))
    db.commit()