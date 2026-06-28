"""业务异常 + FastAPI 异常处理器注册。

设计要点：
    - BizException 携带 code 与 message，service 层主动抛出
    - 全局异常处理器统一捕获，转为标准响应格式
    - RequestValidationError（Pydantic 校验失败）→ 40007
    - 兜底 Exception → 50000，避免敏感堆栈泄露给前端
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import BizCode, error


class BizException(Exception):
    """业务异常：携带 code 与 message，由 service 层主动抛出。

    用法：
        raise BizException(BizCode.USER_NOT_FOUND)
        raise BizException(BizCode.LOGIN_FAILED, "手机号或密码错误")

    异常处理器会捕获并转为 error() 响应。
    """

    def __init__(self, code: int, message: str | None = None, data=None):
        """初始化业务异常。

        Args:
            code: 业务码（BizCode.XXX）
            message: 自定义消息，None 时由响应层使用默认消息
            data: 附加数据（可选）
        """
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message or f"BizException({code})")


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用。

    在 main.py 中调用一次即可生效，处理顺序：
        1. BizException → 业务异常，按 code 映射 HTTP 状态码
        2. RequestValidationError → Pydantic 校验失败，统一 40007
        3. Exception → 未捕获异常兜底，统一 50000
    """

    @app.exception_handler(BizException)
    async def handle_biz_exception(_: Request, exc: BizException) -> JSONResponse:
        """业务异常 → 统一响应格式。"""
        return error(exc.code, exc.message, exc.data)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Pydantic 请求体校验失败 → 40007，附带详细错误列表。

        注意：Pydantic v2 的 exc.errors() 返回的 ctx 字段可能含 ValueError
        等不可 JSON 序列化的对象，会导致 JSONResponse 序列化失败并触发兜底
        50000 错误。此处剥离 ctx 字段保证响应可序列化。
        """
        safe_errors = [
            {k: v for k, v in err.items() if k != "ctx"}
            for err in exc.errors()
        ]
        return error(BizCode.UNPROCESSABLE, data=safe_errors)

    @app.exception_handler(Exception)
    async def handle_unknown_exception(
        _: Request, exc: Exception
    ) -> JSONResponse:
        """未捕获异常兜底 → 50000，避免堆栈泄露。

        生产环境应在此记录完整 traceback 到日志系统。
        """
        # TODO: 接入日志系统记录 exc 与 traceback
        return error(BizCode.INTERNAL_ERROR)
