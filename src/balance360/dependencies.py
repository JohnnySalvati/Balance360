from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from balance360.database import SessionLocal
from balance360.services.auth import decode_access_token
from balance360.crud import user as user_crud

def get_db():
    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            raise e


def get_current_user(
        request: Request,
        db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Token invalido")
    
    try:
        user_id = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token invalido")

    user = user_crud.get_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
