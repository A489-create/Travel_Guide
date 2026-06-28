"""认证模块请求/响应 schema。

字段命名与前端 auth.js 对齐：
    - 请求体：phone/username/name/password（小写）
    - 令牌字段：accessToken/refreshToken（驼峰，前端 localStorage key）
    - 改密字段：oldPassword/newPassword（驼峰，前端 auth.js 传参）
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import UserResponse

# 中国大陆手机号正则：1 开头，第二位 3-9，共 11 位
_PHONE_PATTERN = r"^1[3-9]\d{9}$"


class RegisterRequest(BaseModel):
    """注册请求体。"""

    phone: str = Field(..., description="手机号（11 位）")
    username: str = Field(..., max_length=50, description="用户名")
    name: str = Field(..., max_length=50, description="显示名")
    password: str = Field(..., min_length=6, max_length=128, description="密码（至少 6 位）")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """校验手机号格式：1 开头、11 位数字。"""
        import re

        if not re.match(_PHONE_PATTERN, v):
            raise ValueError("手机号格式不正确")
        return v


class LoginRequest(BaseModel):
    """登录请求体。"""

    phone: str = Field(..., description="手机号")
    password: str = Field(..., description="密码")


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(..., alias="refreshToken", description="Refresh Token")


class ChangePasswordRequest(BaseModel):
    """修改密码请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    old_password: str = Field(..., alias="oldPassword", description="旧密码")
    new_password: str = Field(
        ..., alias="newPassword", min_length=6, max_length=128, description="新密码（至少 6 位）"
    )


class TokenResponse(BaseModel):
    """令牌响应（access + refresh）。"""

    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(..., alias="accessToken", description="Access Token")
    refresh_token: str = Field(..., alias="refreshToken", description="Refresh Token")


class LoginResponse(BaseModel):
    """登录响应：用户信息 + 双 Token。"""

    model_config = ConfigDict(populate_by_name=True)

    user: UserResponse
    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")


class AdminRegisterRequest(RegisterRequest):
    """管理员注册请求体（继承注册字段，增加邀请码）。"""

    invite_code: str = Field(..., alias="inviteCode", description="管理员邀请码")


class UserRoleUpdateRequest(BaseModel):
    """修改用户角色请求体。"""

    role: Literal["admin", "user"] = Field(..., description="目标角色：admin / user")


class UserStatusUpdateRequest(BaseModel):
    """修改用户启用状态请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    is_active: bool = Field(..., alias="isActive", description="是否启用账号")


class AdminResetPasswordRequest(BaseModel):
    """管理员重置用户密码请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    new_password: str = Field(
        ...,
        alias="newPassword",
        min_length=6,
        max_length=128,
        description="新密码（至少 6 位）",
    )
