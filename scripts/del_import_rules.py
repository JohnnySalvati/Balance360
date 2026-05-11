
from balance360.database import SessionLocal
from sqlalchemy import text
with SessionLocal() as db:
    db.execute(text('DELETE FROM import_rules'))
    db.commit()
    print('Listo')