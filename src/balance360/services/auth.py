import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from balance360.database import settings

ALGORITHM = "HS256"
EXPIRE_HOURS = 8


def create_access_token(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise ValueError("Token invalido")

    return uuid.UUID(payload["sub"])
