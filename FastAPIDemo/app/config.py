"""应用配置管理模块。

使用 pydantic-settings 从 .env 读取所有运行时配置，类型安全。
"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置：从 .env 加载，所有字段均带默认值或必填。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # 应用
    APP_NAME: str = "Travel Guide API"

    # 数据库（PostgreSQL + pgvector）
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/travel_guide"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production-please"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 管理员邀请码（用于注册管理员账号）
    ADMIN_INVITE_CODE: str = ""

    # 系统管理员手机号（启动时自动升级该用户为 super_admin）
    SUPER_ADMIN_PHONE: str = ""

    # LLM（DeepSeek 对话生成）
    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Embedding（硅基流动）
    EMBEDDING_PROVIDER: str = "siliconflow"
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"
    EMBEDDING_DIMENSION: int = 1024

    # RAG
    RAG_TOP_K: int = 5

    # CORS：逗号分隔的来源列表
    CORS_ORIGINS: str = "http://localhost:5173"

    @field_validator("CORS_ORIGINS")
    @classmethod
    def normalize_cors_origins(cls, v: str) -> str:
        """规范化 CORS 来源字符串：去除空白。"""
        return ",".join([s.strip() for s in v.split(",") if s.strip()])

    @property
    def cors_origins_list(self) -> List[str]:
        """将 CORS_ORIGINS 字符串拆为列表供 FastAPI 使用。"""
        return self.CORS_ORIGINS.split(",")


@lru_cache
def get_settings() -> Settings:
    """单例获取 Settings 实例，避免重复读取 .env。"""
    return Settings()


# 全局共享配置实例
settings = get_settings()
