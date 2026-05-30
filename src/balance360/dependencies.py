from balance360.database import SessionLocal

def get_db():
    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
