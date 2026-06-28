"""知识库条目表模型（含 pgvector 向量字段）。"""
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Text
from sqlmodel import Field, SQLModel, Column

from app.config import settings
from app.models.base import TimestampMixin


class KnowledgeEntry(TimestampMixin, SQLModel, table=True):
    """知识库条目表：景点介绍/美食推荐/避坑指南，含向量字段用于语义检索。

    设计要点：
        - type: 三种类型 attraction / food / tip
        - destination: 目的地（如"东京"），用于按目的地过滤后再向量检索
        - content: 详细内容文本，向 RAG 上下文拼接使用
        - summary: 摘要，用于列表展示
        - metadata: 结构化元信息（价格区间/营业时间/地址/评分等），JSONB
        - embedding: 1024 维向量（BAAI/bge-large-zh-v1.5 输出）
        - source: 内容来源，ai（AI生成）/ manual（手动录入）
        - enabled: 软删除/禁用开关

    注意：metadata 字段在 Python 中是保留属性名，故模型属性命名为
    metadata_，但数据库列名仍为 metadata（通过 sa_column=Column("metadata", JSON) 指定）。
    """

    __tablename__ = "knowledge_entries"

    id: Optional[int] = Field(default=None, primary_key=True, description="主键")
    type: str = Field(
        max_length=20,
        nullable=False,
        index=True,
        description="条目类型：attraction / food / tip",
    )
    title: str = Field(max_length=200, nullable=False, description="标题")
    destination: str = Field(
        max_length=100,
        nullable=False,
        index=True,
        description="目的地",
    )
    content: str = Field(
        sa_column=Column(Text, nullable=False),
        description="详细内容",
    )
    summary: Optional[str] = Field(
        default=None, max_length=500, description="摘要（列表展示）"
    )
    metadata_: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column("metadata", JSON),
        description="结构化元信息（价格/营业时间/地址等）",
    )
    embedding: Optional[Any] = Field(
        default=None,
        sa_column=Column(Vector(settings.EMBEDDING_DIMENSION)),
        description=f"{settings.EMBEDDING_MODEL} 向量（{settings.EMBEDDING_DIMENSION}维）",
    )
    source: str = Field(
        default="ai", max_length=20, description="来源：ai / manual"
    )
    enabled: bool = Field(
        default=True, nullable=False, description="是否启用"
    )
    owner_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,
        description="归属用户 ID；NULL=系统知识库，非 NULL=个人知识库",
    )
