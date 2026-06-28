"""通用响应 schema。

定义跨模块复用的响应模型，如用户信息。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    """用户信息响应（不含密码哈希等敏感字段）。

    前端在 /auth/me、/auth/login、/auth/register 及管理员用户列表中使用。
    字段统一按 camelCase 输出，以匹配前端 Vue 代码。
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    id: int
    phone: str
    username: str
    name: str
    avatar: Optional[str] = None
    role: str = "user"
    is_active: bool = Field(default=True, alias="isActive", description="账号是否启用")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt", description="注册时间")
