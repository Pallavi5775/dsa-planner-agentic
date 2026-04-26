import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.getenv("SECRET_KEY", "dsa-planner-secret-key-change-in-prod-2026")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

bearer_scheme = HTTPBearer()


def create_access_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "username": username, "role": role, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def _parse_user(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        payload = decode_token(credentials.credentials)
        return {
            "id":       int(payload["sub"]),
            "username": payload.get("username", ""),
            "role":     payload.get("role", "user"),
        }
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    return _parse_user(credentials)


async def get_current_user_id(
    user: dict = Depends(get_current_user),
) -> int:
    return user["id"]


async def require_admin(
    user: dict = Depends(get_current_user),
) -> int:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user["id"]
