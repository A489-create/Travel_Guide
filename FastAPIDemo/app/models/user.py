"""用户表模型。"""
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin


class User(TimestampMixin, SQLModel, table=True):
    """用户表：存储账号信息，phone 唯一作为登录凭证。

    字段：
        phone: 手机号，唯一索引，登录用户名
        username: 用户名（昵称前缀）
        name: 显示名，前端顶部用户下拉使用
        password_hash: bcrypt 哈希后的密码（绝不存明文）
        avatar: 头像 URL（本期不实现上传）
    """

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True, description="主键")
    phone: str = Field(
        max_length=20,
        unique=True,
        index=True,
        nullable=False,
        description="手机号，登录用",
    )
    username: str = Field(max_length=50, nullable=False, description="用户名")
    name: str = Field(max_length=50, nullable=False, description="显示名")
    password_hash: str = Field(
        max_length=255, nullable=False, description="bcrypt 哈希密码"
    )
    avatar: Optional[str] = Field(default=None, max_length=500, description="头像URL")
    role: str = Field(
        default="user",
        max_length=20,
        nullable=False,
        index=True,
        description="角色：admin / user",
    )
    is_active: bool = Field(
        default=True,
        nullable=False,
        description="账号是否启用（False=已封禁）",
    )
