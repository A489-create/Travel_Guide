"""知识库生成任务表模型。"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Text
from sqlmodel import Field, SQLModel, Column

from app.models.base import TimestampMixin


class KnowledgeGenerationTask(TimestampMixin, SQLModel, table=True):
    """记录 AI 批量生成知识库的任务进度。

    由于生成过程较慢（多次调用 LLM + Embedding），采用异步任务模式：
        - 触发生成接口立即返回 task_id
        - 后台执行：对每个 type 调用 DeepSeek 生成内容 + 硅基流动生成向量
        - 前端轮询 /api/knowledge/tasks/{id} 查看进度

    字段：
        destination: 目的地
        types: 要生成的类型数组 ["attraction","food","tip"]
        status: pending / running / completed / failed
        total: 计划生成的总条目数
        success: 已成功数
        failed: 已失败数
        error_msg: 失败原因（如有）
        completed_at: 完成时间（成功或失败）
    """

    __tablename__ = "knowledge_generation_tasks"

    id: Optional[int] = Field(default=None, primary_key=True, description="主键")
    destination: str = Field(
        max_length=100,
        nullable=False,
        index=True,
        description="目的地",
    )
    types: List[str] = Field(
        default_factory=lambda: ["attraction", "food", "tip"],
        sa_column=Column(JSON),
        description="生成类型数组",
    )
    status: str = Field(
        default="pending",
        max_length=20,
        description="pending / running / completed / failed",
    )
    total: int = Field(default=0, nullable=False, description="计划生成数")
    success: int = Field(default=0, nullable=False, description="已成功数")
    failed: int = Field(default=0, nullable=False, description="已失败数")
    error_msg: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="失败原因",
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="完成时间"
    )
    triggered_by: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,
        description="任务触发者 ID；NULL=CLI/系统，非 NULL=触发用户",
    )
