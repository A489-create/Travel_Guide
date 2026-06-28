"""对话消息表模型。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    """消息表：存储对话历史，按 conversation_id 分组、按 id 升序加载。

    不继承 TimestampMixin：消息表只需要 created_at，不需要 updated_at
    （消息发出后不允许修改）。

    字段：
        conversation_id: 所属会话ID，外键 + 索引
        role: 消息角色 user / assistant / system
        content: 消息内容（assistant 完整回复，含 <plan>...</plan> 标记）
    """

    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True, description="主键")
    conversation_id: int = Field(
        foreign_key="conversations.id",
        nullable=False,
        index=True,
        description="所属会话ID",
    )
    role: str = Field(
        max_length=20,
        nullable=False,
        description="消息角色：user / assistant / system",
    )
    content: str = Field(nullable=False, description="消息内容")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
        description="创建时间",
    )
