"""行程模块响应 schema。

字段命名与 travel_plans 表模型对齐：
    - days_plan: 每日行程数组（JSON），前端按日渲染
    - luggage: 行李清单数组（JSON），前端分类展示
    - preferences: 偏好标签数组

3 个 schema：
    - TravelPlanResponse: 行程详情响应
    - TravelListResponse: 分页列表响应（不含 days_plan/luggage 大字段）
    - TravelPlanListItem: 列表项（精简字段）
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class TravelPlanResponse(BaseModel):
    """行程详情响应（含完整 days_plan 与 luggage）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: Optional[int] = None
    title: str
    destination: str
    days: int
    budget: Optional[Decimal] = None
    preferences: Optional[list[str]] = None
    days_plan: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="每日行程数组，结构由 LLM 生成",
    )
    luggage: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="行李清单数组，结构由 LLM 生成",
    )
    created_at: datetime


class TravelPlanListItem(BaseModel):
    """行程列表项（精简，不含 days_plan/luggage 大字段）。

    用于列表展示，减少传输量。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    destination: str
    days: int
    budget: Optional[Decimal] = None
    preferences: Optional[list[str]] = None
    created_at: datetime


class TravelListResponse(BaseModel):
    """分页列表响应：{list, total}。"""

    list: list[TravelPlanListItem]
    total: int


class TravelPlanUpdateRequest(BaseModel):
    """行程更新请求（所有字段可选，仅传需要修改的）。

    用于 PUT /api/travel/{id} 显式更新接口。所有字段可选，
    未提供的字段保留原值。
    """

    title: Optional[str] = Field(default=None, max_length=200)
    days: Optional[int] = Field(default=None, ge=1)
    budget: Optional[Decimal] = None
    preferences: Optional[list[str]] = None
    days_plan: Optional[list[dict[str, Any]]] = None
    luggage: Optional[list[dict[str, Any]]] = None
