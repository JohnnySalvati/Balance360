import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from passlib.context import CryptContext
from balance360.models.user import User
from balance360.schemas.user import UserCreate, UserUpdate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated= "auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def get_all(db: Session) -> list[User]:
    users = db.execute(select(User)).scalars().all()
    return list(users)

def get_by_id(db: Session, user_id: uuid.UUID) -> User|None:
    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    return user

def get_by_email(db: Session, email: str) -> User|None:
    user = db.execute(select(User).where(User.email == email)).scalars().first()
    return user

def create(db: Session, data: UserCreate) -> User:
    hashed = hash_password(data.password)
    db_user = User(
        email = data.email,
        hashed_password = hashed,
        full_name = data.full_name,
        is_active = data.is_active
    )
    db.add(db_user)
    db.flush()
    db.refresh(db_user)
    return db_user

def delete(db: Session, user: User):
    db.delete(user)

def update(db: Session, user: User, data: UserUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.flush()
    db.refresh(user)
    return user

def verify_user_password(user: User, password: str) -> bool:
    return pwd_context.verify(password, user.hashed_password)