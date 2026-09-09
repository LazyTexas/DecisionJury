# backend/security.py
"""
JWT 认证模块

功能说明：
- 双模式设计（兼容模式 / 强制模式），由 ENFORCE_JWT 开关控制
- 密码哈希使用 bcrypt（更安全）
- JWT Token 创建与解码

使用方式：
    from backend.security import get_current_user_optional, create_access_token, get_password_hash, verify_password

    # 生成 Token
    token = create_access_token(data={"sub": user_id})

    # 获取当前用户（自动处理强制模式）
    current_user = Depends(get_current_user_optional)
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.config import Config
from backend.database import get_db
from backend.models import User

# ==================== 密码哈希 ====================

# 使用 bcrypt 算法（比 sha256_crypt 更安全）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否匹配哈希值"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """对密码进行哈希加密"""
    return pwd_context.hash(password)


# ==================== JWT 操作 ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT 访问令牌

    Args:
        data: 要编码到 Token 中的数据，必须包含 "sub"（用户 ID）
        expires_delta: 过期时间，默认使用 Config.ACCESS_TOKEN_EXPIRE_MINUTES

    Returns:
        JWT 字符串
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, Config.SECRET_KEY, algorithm=Config.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """
    解码 JWT Token，提取用户 ID

    Args:
        token: JWT 字符串

    Returns:
        用户 ID，解码失败返回 None
    """
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.ALGORITHM])
        user_id: str = payload.get("sub")
        return user_id
    except JWTError:
        return None


# ==================== OAuth2 方案 ====================

# auto_error=False 是关键：无 Token 时不自动报错，由路由层自行处理
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ==================== 核心依赖 ====================

def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    获取当前用户（由 ENFORCE_JWT 控制行为）

    行为模式：
    - ENFORCE_JWT = True（强制模式）：
        - 无 Token → 抛出 401
        - Token 无效/过期 → 抛出 401
        - 用户不存在 → 抛出 401

    - ENFORCE_JWT = False（兼容模式）：
        - 无 Token → 返回 None
        - Token 无效/过期 → 返回 None
        - 用户不存在 → 返回 None

    路由层使用方式：
        current_user: Optional[User] = Depends(get_current_user_optional)
        effective_user_id = current_user.id if current_user else req.user_id
    """
    # ---- 1. 无 Token 的情况 ----
    if not token:
        if Config.ENFORCE_JWT:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "UNAUTHORIZED",
                    "message": "未提供认证 Token，请登录后重试"
                }
            )
        return None

    # ---- 2. 解析 Token ----
    user_id = decode_access_token(token)
    if user_id is None:
        if Config.ENFORCE_JWT:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_TOKEN",
                    "message": "Token 无效或已过期，请重新登录"
                }
            )
        return None

    # ---- 3. 查询用户 ----
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        if Config.ENFORCE_JWT:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "USER_NOT_FOUND",
                    "message": "用户不存在，Token 无效"
                }
            )
        return None

    return user


# ==================== 便捷函数（仅供测试/内部使用）====================

def get_current_user_required(
    current_user: User = Depends(get_current_user_optional)
) -> User:
    """
    强制获取当前用户（用于需要绝对认证的场景）

    与 get_current_user_optional 的区别：
    - 如果 current_user 为 None，直接抛 401（无论 ENFORCE_JWT 设置如何）
    - 适用于 admin 接口等必须认证的场景
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "请先登录后再访问此接口"
            }
        )
    return current_user