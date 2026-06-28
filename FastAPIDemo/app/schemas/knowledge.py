"""知识库模块请求/响应 schema。

字段命名与前端契约对齐：
    - 响应字段：snake_case，与 KnowledgeEntry 模型一致
    - metadata: 模型属性为 metadata_（Python 保留名），响应中暴露为 metadata
    - 分页字段：page/pageSize（驼峰，前端通用）
    - 检索字段：topK（驼峰，前端传参）

5 个 schema：
    - KnowledgeEntryResponse: 条目详情响应
    - KnowledgeSearchRequest: 向量检索请求
    - KnowledgeGenerateRequest: 触发生成请求
    - KnowledgeTaskResponse: 任务状态响应
    - KnowledgeListResponse: 分页列表响应
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# 知识库支持的条目类型
_VALID_TYPES = ("attraction", "food", "tip")


class KnowledgeEntryResponse(BaseModel):
    """知识库条目响应（不含 embedding 向量，避免传输大量数据）。

    metadata 字段说明：
        - 数据库列名为 metadata（JSONB）
        - SQLModel 模型属性为 metadata_（避免与 Python 保留名冲突）
        - 响应 JSON 中暴露为 metadata，通过 validation_alias 读取模型属性
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    type: str
    title: str
    destination: str
    content: str
    summary: Optional[str] = None
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        validation_alias="metadata_",
        description="结构化元信息（价格/营业时间/地址等）",
    )
    source: str
    enabled: bool
    created_at: datetime
    owner_id: Optional[int] = None


class KnowledgeSearchRequest(BaseModel):
    """向量语义检索请求。

    前端 POST /api/knowledge/search 请求体：
        {
            "query": "东京有什么好玩的",
            "destination": "东京",
            "type": "attraction",   // 可选
            "topK": 5                // 可选，默认 settings.RAG_TOP_K
        }
    """

    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(..., min_length=1, description="检索查询文本")
    destination: str = Field(..., description="目的地过滤")
    type: Optional[str] = Field(
        default=None,
        description="条目类型过滤：attraction / food / tip",
    )
    top_k: Optional[int] = Field(
        default=None,
        alias="topK",
        ge=1,
        le=20,
        description="返回条目数上限，默认 RAG_TOP_K",
    )


class KnowledgeGenerateRequest(BaseModel):
    """触发 AI 生成请求。

    前端 POST /api/knowledge/generate 请求体：
        {
            "destination": "东京",
            "types": ["attraction", "food", "tip"]  // 可选，默认全部
        }
    """

    model_config = ConfigDict(populate_by_name=True)

    destination: str = Field(..., min_length=1, description="目的地名称")
    types: Optional[list[str]] = Field(
        default=None,
        description="生成类型列表，默认 [attraction, food, tip]",
    )


class KnowledgeTaskResponse(BaseModel):
    """生成任务状态响应。

    用于前端轮询 /api/knowledge/tasks/{id} 查看进度。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    destination: str
    types: list[str]
    status: str = Field(description="pending / running / completed / failed")
    total: int
    success: int
    failed: int
    error_msg: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    triggered_by: Optional[int] = None


class KnowledgeListResponse(BaseModel):
    """分页列表响应：{list, total}。"""

    list: list[KnowledgeEntryResponse]
    total: int


class KnowledgeUpdateRequest(BaseModel):
    """知识条目更新请求（所有字段可选）。

    前端 PATCH /api/knowledge/{id} 或 /api/admin/knowledge/{id} 请求体：
        {
            "title": "...",        // 可选
            "content": "...",      // 可选，变更后自动重新计算 embedding
            "summary": "...",      // 可选
            "metadata": {...},     // 可选
            "enabled": true        // 可选，启用/禁用
        }
    """

    model_config = ConfigDict(populate_by_name=True)

    title: Optional[str] = Field(default=None, max_length=200, description="标题")
    content: Optional[str] = Field(default=None, description="详细内容")
    summary: Optional[str] = Field(default=None, max_length=500, description="摘要")
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="结构化元信息（价格/营业时间/地址等）",
    )
    enabled: Optional[bool] = Field(default=None, description="是否启用")
