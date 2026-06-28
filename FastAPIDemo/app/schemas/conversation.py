"""对话模块请求/响应 schema。

字段命名与前端契约对齐（前端使用 camelCase）：
    - 响应字段：snake_case，与模型属性一致
    - 创建会话：title（可选）
    - 发送消息：content

6 个 schema：
    - CreateConversationRequest: 创建会话请求
    - SendMessageRequest: 发送消息请求
    - MessageResponse: 消息响应
    - ConversationResponse: 会话响应
    - ConversationDetailResponse: 会话详情（含消息列表）
    - ConversationListResponse: 分页列表响应
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateConversationRequest(BaseModel):
    """创建会话请求。

    title 可选，为空时由后端从首条消息摘要生成。
    """

    title: Optional[str] = Field(
        default=None,
        max_length=200,
        description="会话标题（可选，为空时从首条消息摘要生成）",
    )


class SetCurrentPlanRequest(BaseModel):
    """设置会话当前行程请求。

    用于在多个历史行程间切换"当前编辑"的行程。
    """

    plan_id: int = Field(..., description="要设为当前行程的 ID")


class PlanActionRequest(BaseModel):
    """确认行程变更保存方式请求。

    当检测到用户意图发生重大变更且已存在当前行程时，
    前端通过此接口告知后端选择"更新当前攻略"还是"创建新攻略"。
    """

    action: Literal["update", "create"] = Field(
        ..., description="保存方式：update 覆盖当前攻略，create 新建攻略"
    )


class SendMessageRequest(BaseModel):
    """发送消息请求。

    前端 POST /api/conversations/{id}/messages 请求体：
        {"content": "我想去东京玩 5 天，预算 1 万，喜欢美食"}
    """

    content: str = Field(..., min_length=1, description="消息内容")


class MessageResponse(BaseModel):
    """消息响应。

    assistant 消息的 content 可能包含 <plan>{...}</plan> 块，
    前端按需解析或后端预先剥离。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime


class ConversationResponse(BaseModel):
    """会话响应（不含消息列表）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    destination: Optional[str] = None
    days: Optional[int] = None
    budget: Optional[Decimal] = None
    preferences: Optional[list[str]] = None
    status: str
    current_plan_id: Optional[int] = None
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    """会话详情：基础字段 + 消息列表。"""

    messages: list[MessageResponse] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    """分页列表响应：{list, total}。"""

    list: list[ConversationResponse]
    total: int
