import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from balance360.models.user import User
from balance360.schemas.user import UserRead, UserCreate, UserUpdate
from balance360.crud.user import get_all, get_by_id, create, delete, update
from balance360.dependencies import get_db

router = APIRouter(prefix="/users", tags=["users"])

def get_user_or_404(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    return get_all(db)

@router.get("/{user_id}", response_model=UserRead)
def get_user(user: User = Depends(get_user_or_404)):
    return user

@router.post("/", response_model=UserRead)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    return create(db, data)

@router.delete("/{user_id}", status_code=204)
def delete_user(user: User = Depends(get_user_or_404), db: Session = Depends(get_db)):
    delete(db, user)

@router.patch("/{user_id}", response_model=UserRead)
def update_user(data: UserUpdate, user: User = Depends(get_user_or_404), db: Session = Depends(get_db)):
    update(db, user, data)