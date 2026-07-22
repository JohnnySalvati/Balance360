from balance360.dependencies import SessionLocal
from balance360.services.rate_sync import sync_uva

with SessionLocal() as db:
    print(sync_uva(db))
    db.commit()
