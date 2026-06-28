"""LLM / Embedding 客户端工厂。

按 settings 中的 LLM_PROVIDER / EMBEDDING_PROVIDER 选择具体实现，
业务层通过工厂获取抽象基类实例，无需感知具体厂商。

用法：
    from app.services.llm.factory import LLMFactory, EmbeddingFactory

    llm = LLMFactory.get_llm()
    embedding = EmbeddingFactory.get_embedding()

后续扩展：
    - 新增厂商：实现对应子类后在此处 if 分支中注册即可
    - 替换模型：仅需修改 .env 的 PROVIDER 配置
"""
from app.config import settings
from app.core.exceptions import BizException
from app.core.response import BizCode

from .base import BaseEmbeddingClient, BaseLLMClient
from .deepseek import DeepSeekClient
from .siliconflow import SiliconFlowEmbeddingClient


class LLMFactory:
    """LLM 客户端工厂。

    根据 settings.LLM_PROVIDER 返回对应实现实例。
    """

    @staticmethod
    def get_llm() -> BaseLLMClient:
        """获取 LLM 客户端实例。

        Returns:
            BaseLLMClient: 具体实现（如 DeepSeekClient）。

        Raises:
            BizException(UPSTREAM_ERROR): 不支持的 provider。
        """
        provider = settings.LLM_PROVIDER.lower()
        if provider == "deepseek":
            return DeepSeekClient()
        raise BizException(
            BizCode.UPSTREAM_ERROR,
            f"不支持的 LLM provider: {settings.LLM_PROVIDER}",
        )


class EmbeddingFactory:
    """Embedding 客户端工厂。

    根据 settings.EMBEDDING_PROVIDER 返回对应实现实例。
    """

    @staticmethod
    def get_embedding() -> BaseEmbeddingClient:
        """获取 Embedding 客户端实例。

        Returns:
            BaseEmbeddingClient: 具体实现（如 SiliconFlowEmbeddingClient）。

        Raises:
            BizException(UPSTREAM_ERROR): 不支持的 provider。
        """
        provider = settings.EMBEDDING_PROVIDER.lower()
        if provider == "siliconflow":
            return SiliconFlowEmbeddingClient()
        raise BizException(
            BizCode.UPSTREAM_ERROR,
            f"不支持的 Embedding provider: {settings.EMBEDDING_PROVIDER}",
        )
