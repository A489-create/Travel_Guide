"""对话会话表模型。"""
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin


class Conversation(TimestampMixin, SQLModel, table=True):
    """对话会话表：一个用户可有多个会话，每个会话关联一次行程规划。

    行程参数字段（destination/days/budget/preferences）从用户首条消息中
    解析后写入，供会话列表展示与 RAG 检索使用。

    字段：
        title: 会话标题，默认从首条消息摘要生成
        destination: 提取出的目的地（如"东京"），用于过滤知识库
        days: 行程天数
        budget: 预算（元）
        preferences: 偏好标签数组（如 ["美食","自然风光"]），用 JSONB 存储
        status: active（活跃）/ archived（归档）
    """

    __tablename__ = "conversations"

    id: Optional[int] = Field(default=None, primary_key=True, description="主键")
    user_id: int = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="所属用户ID",
    )
    title: str = Field(max_length=200, nullable=False, description="会话标题")
    destination: Optional[str] = Field(
        default=None, max_length=100, description="提取的目的地"
    )
    days: Optional[int] = Field(default=None, description="行程天数")
    budget: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        description="预算（元）",
    )
    preferences: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="偏好标签数组",
    )
    status: str = Field(
        default="active", max_length=20, description="active / archived"
    )
    current_plan_id: Optional[int] = Field(
        default=None,
        foreign_key="travel_plans.id",
        description="当前生效的行程ID（用于迭代修改）",
    )
    pending_params: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="检测到的待确认行程参数",
    )
