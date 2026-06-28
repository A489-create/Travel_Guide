"""模型层：所有 SQLModel 表定义。

import 此包会触发所有模型注册到 SQLModel.metadata，
Alembic env.py 与 init_db() 都依赖此 import。
"""
from app.models.base import TimestampMixin
from app.models.user import User
from app.models.token import RefreshToken
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.travel_plan import TravelPlan
from app.models.knowledge import KnowledgeEntry
from app.models.knowledge_task import KnowledgeGenerationTask

__all__ = [
    "TimestampMixin",
    "User",
    "RefreshToken",
    "Conversation",
    "Message",
    "TravelPlan",
    "KnowledgeEntry",
    "KnowledgeGenerationTask",
]
