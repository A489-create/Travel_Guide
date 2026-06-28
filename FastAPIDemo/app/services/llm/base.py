"""LLM 与 Embedding 抽象基类。

设计目的：
    - 面向接口编程，业务层依赖抽象而非具体实现
    - 通过工厂模式按 settings 选择具体实现（DeepSeek / SiliconFlow）
    - 后续替换模型只需新增子类并在工厂中注册即可
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseLLMClient(ABC):
    """对话生成客户端抽象。

    所有 LLM 实现需继承此类并实现 chat_stream，
    以流式 AsyncIterator[str] 形式返回生成文本。
    """

    @abstractmethod
    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """流式返回生成内容（逐 chunk yield）。

        Args:
            messages: OpenAI 消息列表，形如
                [{"role": "system", "content": "..."},
                 {"role": "user", "content": "..."}]

        Yields:
            str: 每次生成的文本片段（delta content）。
        """
        ...


class BaseEmbeddingClient(ABC):
    """嵌入向量客户端抽象。

    所有 Embedding 实现需继承此类并实现 embed，
    返回与输入文本等长的向量列表。
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成向量。

        Args:
            texts: 待向量化的文本列表。

        Returns:
            list[list[float]]: 与 texts 等长的向量列表，
            每条向量维度由具体模型决定（SiliconFlow bge-large-zh 为 1024）。
        """
        ...
