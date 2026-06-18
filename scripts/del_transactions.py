
from balance360.database import SessionLocal
from sqlalchemy import text
with SessionLocal() as db:
    db.execute(text('DELETE FROM transactions'))
    db.commit()
    print('Listo')