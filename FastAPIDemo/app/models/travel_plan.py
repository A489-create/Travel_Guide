"""旅游攻略表模型。"""
from datetime import date
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin


class TravelPlan(TimestampMixin, SQLModel, table=True):
    """旅游攻略表：存储生成的结构化行程。

    一条 TravelPlan 由对话会话中 assistant 输出的 <plan>{...}</plan>
    JSON 块解析生成，关联 conversation_id 用于追溯来源。

    字段：
        conversation_id: 关联会话（可空，预留未来直接创建）
        days: 天数
        budget: 预算（元）
        preferences: 偏好标签数组
        days_plan: 每日行程数组（JSON），结构与前端一致
        luggage: 行李清单数组（JSON），结构与前端一致

    days_plan 结构：
        [{"day": 1, "title": "...", "activities": [...],
          "meals": "...", "notes": "..."}]

    luggage 结构：
        [{"category": "...", "items": [...], "tips": "..."}]
    """

    __tablename__ = "travel_plans"

    id: Optional[int] = Field(default=None, primary_key=True, description="主键")
    user_id: int = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="所属用户ID",
    )
    conversation_id: Optional[int] = Field(
        default=None,
        foreign_key="conversations.id",
        description="关联会话ID（可空）",
    )
    title: str = Field(max_length=200, nullable=False, description="攻略标题")
    destination: str = Field(max_length=100, nullable=False, description="目的地")
    days: int = Field(nullable=False, description="行程天数")
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
    days_plan: Optional[List[dict[str, Any]]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="每日行程数组",
    )
    luggage: Optional[List[dict[str, Any]]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="行李清单数组",
    )
