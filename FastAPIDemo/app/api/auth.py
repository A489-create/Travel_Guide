"""认证模块路由。

端点清单（前缀 /api/auth）：
    POST /auth/register        注册
    POST /auth/login           登录（返回双 Token）
    POST /auth/refresh-token   刷新 Token
    POST /auth/logout          登出（吊销 Token）
    GET  /auth/me              获取当前用户信息
    PUT  /auth/change-password 修改密码

响应格式统一为 {code, message, data}，data 结构与前端 auth.js 契约对齐。
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.response import success
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    AdminRegisterRequest,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register")
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    """用户注册。

    请求体：{phone, username, name, password}
    响应 data：UserResponse
    """
    user = auth_service.register(
        db,
        phone=body.phone,
        username=body.username,
        name=body.name,
        password=body.password,
    )
    return success(UserResponse.model_validate(user).model_dump())


@router.post("/register-admin")
def register_admin(
    body: AdminRegisterRequest,
    db: Session = Depends(get_db),
):
    """管理员注册（需邀请码）。

    请求体：{phone, username, name, password, inviteCode}
    响应 data：UserResponse（role=admin）
    """
    user = auth_service.register_admin(
        db,
        phone=body.phone,
        username=body.username,
        name=body.name,
        password=body.password,
        invite_code=body.invite_code,
    )
    return success(UserResponse.model_validate(user).model_dump())


@router.post("/login")
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    """用户登录。

    请求体：{phone, password}
    响应 data：{user, accessToken, refreshToken}
    """
    user, access_token, refresh_token = auth_service.login(
        db, phone=body.phone, password=body.password
    )
    response = LoginResponse(
        user=UserResponse.model_validate(user),
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return success(response.model_dump(by_alias=True))


@router.post("/refresh-token")
def refresh_token(
    body: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """刷新 Access Token。

    请求体：{refreshToken}
    响应 data：{accessToken, refreshToken}
    """
    new_access, new_refresh = auth_service.refresh_tokens(
        db, refresh_token=body.refresh_token
    )
    response = TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
    )
    return success(response.model_dump(by_alias=True))


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户登出：吊销当前用户所有有效 Refresh Token。"""
    auth_service.logout(db, user_id=current_user.id)
    return success()


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return success(UserResponse.model_validate(current_user).model_dump())


@router.put("/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改密码。

    请求体：{oldPassword, newPassword}
    """
    auth_service.change_password(
        db,
        user_id=current_user.id,
        old_password=body.old_password,
        new_password=body.new_password,
    )
    return success()
