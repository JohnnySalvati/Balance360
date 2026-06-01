from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import uuid

SECRET_KEY = "Esta es una frase muy linda que no voy a contar"
ALGORITHM = "HS256"
EXPIRE_HOURS = 8

def create_access_token(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise ValueError("Token invalido")
    
    return uuid.UUID(payload["sub"])