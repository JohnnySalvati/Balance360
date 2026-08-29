import uuid
from datetime import datetime, timezone

from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from balance360.models.user import User
from balance360.schemas.user import UserCreate, UserUpdate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def get_all(db: Session, search: str | None = None) -> list[User]:
    stmt = select(User)

    if search:
        stmt = stmt.where(User.full_name.ilike(f"%{search}%"))

    users = db.execute(stmt).scalars().all()
    return sorted(list(users), key=lambda x: x.email)


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    return user


def get_by_email(db: Session, email: str) -> User | None:
    """El usuario de esa dirección, sin importar mayúsculas ni espacios alrededor.

    Comparaba con `==` sobre el texto tal cual, así que "Miguel@..." y "  miguel@..." no
    encontraban al usuario de "miguel@...". Del otro lado eso no se ve como "no te encontré":
    se ve como "mail o contraseña incorrectos" —el login y `/api/tokens` contestan lo mismo
    para las dos cosas— y manda a cambiar una contraseña que estaba bien.

    Un mail no distingue mayúsculas en la parte del dominio y, en la práctica, tampoco en la
    del buzón: ningún proveedor que use esta app entrega distinto por eso. Lo que sí hace
    tratarlas como distintas es dejar entrar dos cuentas para la misma persona.
    """
    normalized = email.strip().lower()
    return db.execute(select(User).where(func.lower(User.email) == normalized)).scalars().first()


def create(db: Session, data: UserCreate) -> User:
    hashed = hash_password(data.password)
    db_user = User(
        email=data.email, hashed_password=hashed, full_name=data.full_name, is_active=data.is_active
    )
    db.add(db_user)
    db.flush()
    db.refresh(db_user)
    return db_user


def create_with_hash(
    db: Session, email: str, hashed_password: str, full_name: str, is_active: bool
) -> User:
    """Igual que `create`, pero recibe la contraseña **ya hasheada**.

    Existe para el registro público, que calcula el hash antes de mirar la base a propósito:
    es lo más caro del camino, y hacerlo solo en la rama que crea el usuario haría que una
    dirección ya registrada conteste notoriamente más rápido que una nueva. Con `create` habría
    que hashear dos veces o tirar el primero, y las dos cosas rompen justamente el reloj que se
    está tratando de emparejar.
    """
    db_user = User(
        email=email, hashed_password=hashed_password, full_name=full_name, is_active=is_active
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


def mark_email_confirmed(db: Session, user: User) -> User:
    """Deja constancia de que el dueño de la casilla abrió el link.

    Idempotente: si ya estaba confirmada no se pisa la fecha. La primera es la que cuenta —es
    cuándo se probó que la dirección es suya— y sobreescribirla con la de un segundo click
    borraría el único dato que la columna tiene para dar.
    """
    if user.email_confirmed_at is None:
        user.email_confirmed_at = datetime.now(timezone.utc)
        db.flush()
    return user


def set_password(db: Session, user: User, new_password: str) -> User:
    user.hashed_password = hash_password(new_password)
    db.flush()
    db.refresh(user)
    return user
