import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from passlib.context import CryptContext
from balance360.models.user import User
from balance360.schemas.user import UserCreate, UserUpdate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated= "auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def get_all(db: Session, search: str|None=None) -> list[User]:
    stmt = select(User)

    if search:
        stmt = stmt.where(User.full_name.ilike(f"%{search}%"))
        
    users = db.execute(stmt).scalars().all()
    return sorted(list(users), key=lambda x: x.email)

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
    db.flush()

def update(db: Session, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.flush()
    db.refresh(user)
    return user

def verify_user_password(user: User, password: str) -> bool:
    return pwd_context.verify(password, user.hashed_password)

def set_password(db: Session, user: User, new_password: str) -> User:
    user.hashed_password = hash_password(new_password)
    db.flush()
    db.refresh(user)
    return user
