"""
Authentication and authorization utilities
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.permissions import ensure_admin, is_super_admin
from core.response import UnifiedException
from db.session import get_db
from models.models import User, AccessToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
LOGIN_SESSION_PREFIX = "__login_session__:"


async def revoke_login_sessions(db: AsyncSession, user_id: int) -> int:
    """立即失效用户的网页登录会话，供退出、停用和改密场景复用。"""
    result = await db.execute(
        update(AccessToken)
        .where(
            AccessToken.user_id == user_id,
            AccessToken.name.like(f"{LOGIN_SESSION_PREFIX}%"),
            AccessToken.is_active == True,
            AccessToken.is_deleted == False,
        )
        .values(
            is_active=False,
            is_deleted=True,
            deleted_at=datetime.now(timezone.utc),
        )
    )
    return result.rowcount or 0


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希值"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 过期时间只精确到秒，同一用户同秒登录两次会算出完全相同的令牌，
    # 撞上令牌表的唯一索引导致后一次请求失败，因此加入随机标识保证唯一。
    to_encode.update({"exp": expire, "jti": secrets.token_hex(8)})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前用户"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        phone: str = payload.get("sub")
        if phone is None:
            raise UnifiedException(code=401, message="未授权，请重新登录")
    except JWTError:
        raise UnifiedException(code=401, message="未授权，请重新登录")

    from sqlalchemy import select
    session_result = await db.execute(
        select(AccessToken).where(
            AccessToken.token == token,
            AccessToken.is_active == True,
            AccessToken.is_deleted == False,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session or not session.name or not session.name.startswith(LOGIN_SESSION_PREFIX):
        raise UnifiedException(code=401, message="登录状态已失效，请重新登录")
    if session.expires_at:
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise UnifiedException(code=401, message="登录状态已失效，请重新登录")

    result = await db.execute(select(User).where(User.phone == phone, User.is_deleted == False))
    user = result.scalar_one_or_none()

    if user is None or session.user_id != user.id:
        raise UnifiedException(code=401, message="未授权，请重新登录")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前激活用户"""
    if not current_user.is_active:
        raise UnifiedException(code=403, message="您的账号已被禁用，如有疑问可通过页面右上角问题反馈联系我们")
    if current_user.is_deleted:
        raise UnifiedException(code=403, message="用户已被删除")
    return current_user


async def check_manager_permission(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """检查用户是否具有管理员权限"""
    ensure_admin(current_user)
    return current_user


async def check_super_admin_permission(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """检查用户是否具有超级管理员权限"""
    if not is_super_admin(current_user):
        raise UnifiedException(code=403, message="权限不足")
    return current_user
