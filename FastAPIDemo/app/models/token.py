"""刷新令牌表模型。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin


class RefreshToken(TimestampMixin, SQLModel, table=True):
    """刷新令牌表：支持 JWT 双 Token 机制与主动吊销。

    设计要点：
        - 仅存储 token_hash（SHA256 哈希），不存明文，防止数据库泄露后被利用
        - is_revoked 字段实现登出后立即吊销
        - expires_at 决定过期时间，过期后即使未吊销也无效

    流程：
        - 登录 → 签发 access + refresh，refresh 哈希后入库
        - 401 → 用 refresh 调刷新接口，校验有效且未吊销 → 签发新对，旧 refresh 标记 revoked
        - 登出 → 当前 refresh 标记 revoked
    """

    __tablename__ = "refresh_tokens"

    id: Optional[int] = Field(default=None, primary_key=True, description="主键")
    user_id: int = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="关联用户ID",
    )
    token_hash: str = Field(
        max_length=255,
        unique=True,
        index=True,
        nullable=False,
        description="refresh token 的 SHA256 哈希",
    )
    expires_at: datetime = Field(nullable=False, description="过期时间")
    is_revoked: bool = Field(
        default=False, nullable=False, description="是否已吊销"
    )
