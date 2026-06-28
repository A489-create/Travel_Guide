"""DeepSeek 对话生成实现（OpenAI 兼容协议 + 流式 SSE）。

调用 DeepSeek /v1/chat/completions 接口：
    POST {DEEPSEEK_BASE_URL}/chat/completions
    Headers: Authorization: Bearer {DEEPSEEK_API_KEY}
    Body:
        {
            "model": "deepseek-chat",
            "messages": [...],
            "stream": true,
            "temperature": 0.7
        }

响应为 SSE 流，每行形如：
    data: {"choices":[{"delta":{"content":"片"}}]}

    data: [DONE]
"""
import json
from collections.abc import AsyncIterator

import httpx

from app.config import settings
from app.core.exceptions import BizException
from app.core.response import BizCode

from .base import BaseLLMClient

# 流式请求默认超时（DeepSeek 长响应可能较慢，给宽松上限）
_STREAM_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


class DeepSeekClient(BaseLLMClient):
    """DeepSeek Chat 客户端。

    调用 OpenAI 兼容的 /v1/chat/completions 流式接口，
    逐 chunk 解析 SSE 数据并 yield 文本片段。
    """

    @property
    def _endpoint(self) -> str:
        """拼接 chat/completions 完整 URL。"""
        base = settings.DEEPSEEK_BASE_URL.rstrip("/")
        return f"{base}/chat/completions"

    @property
    def _headers(self) -> dict[str, str]:
        """构造请求头，含 Bearer 鉴权。"""
        return {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    def _build_payload(self, messages: list[dict]) -> dict:
        """构造请求体。

        Args:
            messages: OpenAI 消息列表。

        Returns:
            dict: 请求体，含 model/messages/stream/temperature。
        """
        return {
            "model": settings.DEEPSEEK_MODEL,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
        }

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """流式调用 DeepSeek，逐 chunk 返回文本。

        Args:
            messages: OpenAI 消息列表，role ∈ system/user/assistant。

        Yields:
            str: 文本片段（delta.content），可能为空字符串。

        Raises:
            BizException(LLM_CALL_FAILED): 网络/HTTP 错误或 API 返回非 200。
        """
        if not settings.DEEPSEEK_API_KEY:
            # 配置缺失属于运行时配置错误，归为 LLM 调用失败
            raise BizException(BizCode.LLM_CALL_FAILED, "DeepSeek API Key 未配置")

        payload = self._build_payload(messages)

        try:
            async with httpx.AsyncClient(timeout=_STREAM_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    self._endpoint,
                    headers=self._headers,
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        # 读取错误响应正文用于排错
                        error_body = await response.aread()
                        raise BizException(
                            BizCode.LLM_CALL_FAILED,
                            f"DeepSeek 返回 {response.status_code}: "
                            f"{error_body.decode('utf-8', errors='ignore')[:200]}",
                        )

                    # 逐行解析 SSE
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[len("data:"):].strip()
                        if data_str == "[DONE]":
                            # 流结束信号
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            # 跳过无法解析的行（如心跳注释）
                            continue
                        # 提取 delta.content
                        try:
                            delta = chunk["choices"][0]["delta"].get("content")
                        except (KeyError, IndexError):
                            continue
                        if delta:
                            yield delta
        except httpx.HTTPError as exc:
            raise BizException(
                BizCode.LLM_CALL_FAILED,
                f"DeepSeek 网络错误: {exc}",
            ) from exc
