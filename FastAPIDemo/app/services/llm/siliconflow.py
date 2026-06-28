"""硅基流动 SiliconFlow Embedding 实现。

调用 SiliconFlow /v1/embeddings 接口（OpenAI 兼容协议）：
    POST {SILICONFLOW_BASE_URL}/embeddings
    Headers: Authorization: Bearer {SILICONFLOW_API_KEY}
    Body:
        {
            "model": "BAAI/bge-large-zh-v1.5",
            "input": ["文本1", "文本2", ...]
        }

响应示例：
    {
        "data": [
            {"embedding": [0.01, -0.02, ...], "index": 0},
            {"embedding": [0.03, -0.04, ...], "index": 1}
        ],
        "model": "BAAI/bge-large-zh-v1.5",
        "usage": {...}
    }

输出向量维度由模型决定（bge-large-zh-v1.5 → 1024 维）。
"""
import httpx

from app.config import settings
from app.core.exceptions import BizException
from app.core.response import BizCode

from .base import BaseEmbeddingClient

# Embedding 请求超时（批量向量生成通常较快，但留余量）
_EMBED_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)


class SiliconFlowEmbeddingClient(BaseEmbeddingClient):
    """硅基流动 Embedding 客户端。

    模型 BAAI/bge-large-zh-v1.5，输出 1024 维向量，
    支持 OpenAI 兼容协议的批量 embedding 调用。
    """

    @property
    def _endpoint(self) -> str:
        """拼接 embeddings 完整 URL。"""
        base = settings.SILICONFLOW_BASE_URL.rstrip("/")
        return f"{base}/embeddings"

    @property
    def _headers(self) -> dict[str, str]:
        """构造请求头，含 Bearer 鉴权。"""
        return {
            "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, texts: list[str]) -> dict:
        """构造请求体。

        Args:
            texts: 待向量化的文本列表。

        Returns:
            dict: 请求体，含 model/input。
        """
        return {
            "model": settings.EMBEDDING_MODEL,
            "input": texts,
        }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成向量。

        Args:
            texts: 待向量化的文本列表。

        Returns:
            list[list[float]]: 与 texts 等长的向量列表，
            每条向量维度为 1024（由 bge-large-zh-v1.5 决定）。

        Raises:
            BizException(EMBEDDING_CALL_FAILED): API Key 未配置、
                HTTP 错误或响应结构异常。
        """
        if not texts:
            # 空输入直接返回空列表，避免无意义的网络请求
            return []

        if not settings.SILICONFLOW_API_KEY:
            raise BizException(
                BizCode.EMBEDDING_CALL_FAILED,
                "SiliconFlow API Key 未配置",
            )

        payload = self._build_payload(texts)

        try:
            async with httpx.AsyncClient(timeout=_EMBED_TIMEOUT) as client:
                response = await client.post(
                    self._endpoint,
                    headers=self._headers,
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise BizException(
                BizCode.EMBEDDING_CALL_FAILED,
                f"SiliconFlow 网络错误: {exc}",
            ) from exc

        if response.status_code != 200:
            raise BizException(
                BizCode.EMBEDDING_CALL_FAILED,
                f"SiliconFlow 返回 {response.status_code}: "
                f"{response.text[:200]}",
            )

        data = response.json().get("data")
        if not data or len(data) != len(texts):
            raise BizException(
                BizCode.EMBEDDING_CALL_FAILED,
                f"SiliconFlow 响应条数不匹配：期望 {len(texts)}，"
                f"实际 {len(data) if data else 0}",
            )

        # 按 index 排序后提取 embedding，确保与输入顺序一致
        data.sort(key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in data]
