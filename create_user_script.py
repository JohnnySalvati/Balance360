from balance360.database import SessionLocal
from balance360.crud.user import create
from balance360.schemas.user import UserCreate

with SessionLocal() as db:
    create(db, UserCreate(
        email="miguelsalvati@gmail.com",
        password="lunaynariz",
        full_name="Miguel Salvati",
        is_active=True,
    ))
    db.commit()