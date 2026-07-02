"""
Auth module: đăng nhập, JWT, phân quyền Admin / User.
User lưu dạng flat-file JSON (users.json), mật khẩu hash bằng bcrypt.
Không dùng database vì scope hiện tại là single-node self-host (giống mô hình reviews.json
đã dùng ở project trường học trước đây).
"""
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from backend.config import settings
from backend.core.logger import get_logger

logger = get_logger("auth")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

_lock = threading.Lock()


class UserOut(BaseModel):
    username: str
    role: str  # "admin" | "user"


class TokenData(BaseModel):
    username: str
    role: str


def _load_users() -> dict:
    path: Path = settings.users_file
    if not path.exists():
        # Tạo admin mặc định lần đầu chạy. Mật khẩu phải đổi ngay sau khi deploy.
        default = {
            "admin": {
                "username": "admin",
                "hashed_password": pwd_context.hash("admin123"),
                "role": "admin",
            }
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.warning("Đã tạo tài khoản admin mặc định (admin/admin123). Hãy đổi mật khẩu ngay.")
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save_users(users: dict):
    with _lock:
        settings.users_file.write_text(
            json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def create_user(username: str, password: str, role: str = "user"):
    users = _load_users()
    if username in users:
        raise HTTPException(status_code=400, detail="Tài khoản đã tồn tại")
    users[username] = {
        "username": username,
        "hashed_password": pwd_context.hash(password),
        "role": role,
    }
    _save_users(users)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    if not pwd_context.verify(password, user["hashed_password"]):
        return None
    return user


def create_access_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không xác thực được người dùng",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        return TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception


def require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Yêu cầu quyền Admin")
    return current_user
