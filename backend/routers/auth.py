# backend/routers/auth.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database import get_db
from backend.models import User
from backend.schemas import ApiResponse
from backend.security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


# ===== 请求模型 =====
class RegisterRequest(BaseModel):
    user_id: str
    name: str
    password: str


class LoginRequest(BaseModel):
    user_id: str
    password: str


# ===== 注册接口 =====
@router.post("/register", response_model=ApiResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # 1. 检查用户是否已存在
    existing = db.query(User).filter(User.id == req.user_id).first()
    if existing:
        return ApiResponse(
            success=False,
            data=None,
            message="用户已存在"
        )

    # 2. 哈希加密密码（使用 bcrypt）
    hashed = get_password_hash(req.password)

    # 3. 创建用户
    user = User(
        id=req.user_id,
        name=req.name,
        hashed_password=hashed
    )
    db.add(user)
    db.commit()

    return ApiResponse(
        success=True,
        data={"user_id": user.id, "name": user.name},
        message="注册成功"
    )


# ===== 登录接口 =====
@router.post("/login", response_model=ApiResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # 1. 查询用户
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        return ApiResponse(
            success=False,
            data=None,
            message="用户不存在"
        )

    # 2. 验证密码（使用 bcrypt）
    if not verify_password(req.password, user.hashed_password):
        return ApiResponse(
            success=False,
            data=None,
            message="密码错误"
        )

    # 3. 生成 JWT Token
    access_token = create_access_token(data={"sub": user.id})

    return ApiResponse(
        success=True,
        data={
            "user_id": user.id,
            "name": user.name,
            "access_token": access_token,
            "token_type": "bearer"
        },
        message="登录成功"
    )