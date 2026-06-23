
from balance360.database import SessionLocal
from sqlalchemy import text
with SessionLocal() as db:
    db.execute(text('DELETE FROM transactions'))
    db.execute(text('DELETE FROM import_rules'))
    db.execute(text('DELETE FROM import_rows'))
    db.execute(text('DELETE FROM import_batches'))
    db.commit()
    print('Listo')