from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from database import get_db
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequiredException(Exception):
    pass


class PermissionDeniedException(Exception):
    pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("$2y$"):
        hashed_password = "$2b$" + hashed_password[4:]
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _extract_user(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_sub": False})
        user_id = payload.get("sub")
        if user_id is None:
            return None
        user_id = int(user_id)
    except (JWTError, ValueError, TypeError):
        return None
    return db.query(User).filter(User.id == user_id, User.status == 1).first()


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    return _extract_user(request, db)


def require_login(request: Request, db: Session = Depends(get_db)) -> User:
    user = _extract_user(request, db)
    if not user:
        raise LoginRequiredException()
    return user


def require_roles(*roles):
    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        user = _extract_user(request, db)
        if not user:
            raise LoginRequiredException()
        if user.role not in roles:
            raise PermissionDeniedException()
        return user
    return dependency
