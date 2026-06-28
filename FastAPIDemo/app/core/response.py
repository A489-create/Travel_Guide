"""统一响应工具与业务码枚举。

设计要点：
    - 所有接口（含错误）统一返回 {code, message, data} 结构
    - code 为业务码：0 成功，非 0 失败（5 位编码，分段管理）
    - HTTP 状态码与业务 code 配合：HTTP 反映 HTTP 语义，
      业务 code 提供更细粒度的错误分支判断
    - 前端 request.js 成功时取 response.data.data，错误时取
      error.response.data.message 抛 Error

业务码分段：
    通用段：0, 40000-40008, 50000-50002
    认证段：10001-10007
    对话/行程段：20001-20008
    知识库段：30001-30006
"""
from typing import Any

from fastapi.responses import JSONResponse


class BizCode:
    """业务状态码枚举。

    命名规则：模块前缀_语义。常量值与 HTTP 状态码配合使用，
    通过 _CODE_TO_HTTP 字典映射。
    """

    # ===== 通用段 =====
    SUCCESS = 0  # 成功
    BAD_REQUEST = 40000  # 请求参数错误
    UNAUTHORIZED = 40001  # 未登录或 Token 缺失
    TOKEN_INVALID = 40002  # Access Token 无效或过期
    REFRESH_TOKEN_INVALID = 40003  # Refresh Token 无效或过期
    FORBIDDEN = 40004  # 无权限访问该资源
    NOT_FOUND = 40005  # 资源不存在
    CONFLICT = 40006  # 资源冲突
    UNPROCESSABLE = 40007  # 请求体无法解析（Pydantic 校验失败）
    RATE_LIMIT = 40008  # 请求过于频繁
    INTERNAL_ERROR = 50000  # 服务器内部错误
    UPSTREAM_ERROR = 50001  # 上游服务错误（LLM/Embedding 不可达）
    SERVICE_UNAVAILABLE = 50002  # 服务不可用（数据库连接失败等）

    # ===== 认证段（1xxxx）=====
    PHONE_INVALID = 10001  # 手机号格式不正确
    USERNAME_TOO_LONG = 10002  # 用户名长度超限
    PASSWORD_TOO_SHORT = 10003  # 密码长度不足 6 位
    PHONE_ALREADY_REGISTERED = 10004  # 该手机号已注册
    LOGIN_FAILED = 10005  # 手机号或密码错误
    OLD_PASSWORD_WRONG = 10006  # 旧密码不正确
    USER_NOT_FOUND = 10007  # 用户不存在
    ADMIN_INVITE_CODE_INVALID = 10008  # 管理员邀请码无效
    USER_ROLE_INVALID = 10009  # 用户角色值无效
    USER_DISABLED = 10010  # 账号已被禁用

    # ===== 对话/行程段（2xxxx）=====
    CONV_TITLE_EMPTY = 20001  # 会话标题不能为空
    CONV_NOT_FOUND = 20002  # 会话不存在
    CONV_FORBIDDEN = 20003  # 无权操作该会话
    MSG_CONTENT_EMPTY = 20004  # 消息内容不能为空
    PLAN_NOT_FOUND = 20005  # 行程不存在
    PLAN_FORBIDDEN = 20006  # 无权操作该行程
    LLM_CALL_FAILED = 20007  # LLM 调用失败
    LLM_PARSE_FAILED = 20008  # LLM 响应解析失败

    # ===== 知识库段（3xxxx）=====
    KNOWLEDGE_DEST_EMPTY = 30001  # 目的地不能为空
    KNOWLEDGE_TYPE_INVALID = 30002  # 类型无效
    KNOWLEDGE_NOT_FOUND = 30003  # 知识条目不存在
    KNOWLEDGE_TASK_RUNNING = 30004  # 已有生成任务进行中
    EMBEDDING_CALL_FAILED = 30005  # Embedding 服务调用失败
    VECTOR_SEARCH_FAILED = 30006  # 向量检索失败
    KNOWLEDGE_FORBIDDEN = 30007  # 无权操作该知识条目
    KNOWLEDGE_SCOPE_INVALID = 30008  # scope 参数无效


# 业务码 → HTTP 状态码映射
# 用于 error() 函数构造 JSONResponse 时设置正确的 HTTP 状态码
_CODE_TO_HTTP: dict[int, int] = {
    # 通用段
    BizCode.SUCCESS: 200,
    BizCode.BAD_REQUEST: 400,
    BizCode.UNAUTHORIZED: 401,
    BizCode.TOKEN_INVALID: 401,
    BizCode.REFRESH_TOKEN_INVALID: 401,
    BizCode.FORBIDDEN: 403,
    BizCode.NOT_FOUND: 404,
    BizCode.CONFLICT: 409,
    BizCode.UNPROCESSABLE: 422,
    BizCode.RATE_LIMIT: 429,
    BizCode.INTERNAL_ERROR: 500,
    BizCode.UPSTREAM_ERROR: 502,
    BizCode.SERVICE_UNAVAILABLE: 503,
    # 认证段
    BizCode.PHONE_INVALID: 400,
    BizCode.USERNAME_TOO_LONG: 400,
    BizCode.PASSWORD_TOO_SHORT: 400,
    BizCode.PHONE_ALREADY_REGISTERED: 409,
    BizCode.LOGIN_FAILED: 401,
    BizCode.OLD_PASSWORD_WRONG: 401,
    BizCode.USER_NOT_FOUND: 404,
    BizCode.ADMIN_INVITE_CODE_INVALID: 400,
    BizCode.USER_ROLE_INVALID: 400,
    BizCode.USER_DISABLED: 403,
    # 对话/行程段
    BizCode.CONV_TITLE_EMPTY: 400,
    BizCode.CONV_NOT_FOUND: 404,
    BizCode.CONV_FORBIDDEN: 403,
    BizCode.MSG_CONTENT_EMPTY: 400,
    BizCode.PLAN_NOT_FOUND: 404,
    BizCode.PLAN_FORBIDDEN: 403,
    BizCode.LLM_CALL_FAILED: 502,
    BizCode.LLM_PARSE_FAILED: 502,
    # 知识库段
    BizCode.KNOWLEDGE_DEST_EMPTY: 400,
    BizCode.KNOWLEDGE_TYPE_INVALID: 400,
    BizCode.KNOWLEDGE_NOT_FOUND: 404,
    BizCode.KNOWLEDGE_TASK_RUNNING: 409,
    BizCode.EMBEDDING_CALL_FAILED: 502,
    BizCode.VECTOR_SEARCH_FAILED: 502,
    BizCode.KNOWLEDGE_FORBIDDEN: 403,
    BizCode.KNOWLEDGE_SCOPE_INVALID: 400,
}


# 业务码 → 默认中文消息
# 调用 error() 时若未传 message，使用此默认消息
_DEFAULT_MESSAGE: dict[int, str] = {
    BizCode.SUCCESS: "success",
    BizCode.BAD_REQUEST: "请求参数错误",
    BizCode.UNAUTHORIZED: "未登录或登录已过期",
    BizCode.TOKEN_INVALID: "Access Token 无效或已过期",
    BizCode.REFRESH_TOKEN_INVALID: "Refresh Token 无效或已过期",
    BizCode.FORBIDDEN: "无权限访问该资源",
    BizCode.NOT_FOUND: "资源不存在",
    BizCode.CONFLICT: "资源冲突",
    BizCode.UNPROCESSABLE: "请求参数校验失败",
    BizCode.RATE_LIMIT: "请求过于频繁，请稍后再试",
    BizCode.INTERNAL_ERROR: "服务器内部错误",
    BizCode.UPSTREAM_ERROR: "上游服务暂时不可用",
    BizCode.SERVICE_UNAVAILABLE: "服务暂时不可用",
    BizCode.PHONE_INVALID: "手机号格式不正确",
    BizCode.USERNAME_TOO_LONG: "用户名长度超限",
    BizCode.PASSWORD_TOO_SHORT: "密码长度不足 6 位",
    BizCode.PHONE_ALREADY_REGISTERED: "该手机号已注册",
    BizCode.LOGIN_FAILED: "手机号或密码错误",
    BizCode.OLD_PASSWORD_WRONG: "旧密码不正确",
    BizCode.USER_NOT_FOUND: "用户不存在",
    BizCode.ADMIN_INVITE_CODE_INVALID: "管理员邀请码无效",
    BizCode.USER_ROLE_INVALID: "用户角色值无效，必须是 admin / user",
    BizCode.USER_DISABLED: "账号已被禁用",
    BizCode.CONV_TITLE_EMPTY: "会话标题不能为空",
    BizCode.CONV_NOT_FOUND: "会话不存在",
    BizCode.CONV_FORBIDDEN: "无权操作该会话",
    BizCode.MSG_CONTENT_EMPTY: "消息内容不能为空",
    BizCode.PLAN_NOT_FOUND: "行程不存在",
    BizCode.PLAN_FORBIDDEN: "无权操作该行程",
    BizCode.LLM_CALL_FAILED: "LLM 服务调用失败",
    BizCode.LLM_PARSE_FAILED: "LLM 响应解析失败",
    BizCode.KNOWLEDGE_DEST_EMPTY: "目的地不能为空",
    BizCode.KNOWLEDGE_TYPE_INVALID: "类型无效，必须是 attraction/food/tip",
    BizCode.KNOWLEDGE_NOT_FOUND: "知识条目不存在",
    BizCode.KNOWLEDGE_TASK_RUNNING: "已有生成任务进行中",
    BizCode.EMBEDDING_CALL_FAILED: "Embedding 服务调用失败",
    BizCode.VECTOR_SEARCH_FAILED: "向量检索失败",
    BizCode.KNOWLEDGE_FORBIDDEN: "无权操作该知识条目",
    BizCode.KNOWLEDGE_SCOPE_INVALID: "scope 参数无效，必须是 system / mine / all",
}


def success(data: Any = None, message: str = "success") -> dict:
    """构造成功响应字典。

    用于路由 return 时直接返回，FastAPI 会序列化为 JSON。
    HTTP 状态码默认 200。

    示例：
        return success({"id": 1})
        → {"code": 0, "message": "success", "data": {"id": 1}}
    """
    return {"code": BizCode.SUCCESS, "message": message, "data": data}


def error(code: int, message: str | None = None, data: Any = None) -> JSONResponse:
    """构造错误响应（带正确 HTTP 状态码）。

    Args:
        code: 业务码（BizCode.XXX）
        message: 自定义消息，为 None 时使用默认消息
        data: 附加数据（如校验错误详情），默认 None

    Returns:
        JSONResponse，HTTP 状态码根据 _CODE_TO_HTTP 映射
    """
    return JSONResponse(
        status_code=_CODE_TO_HTTP.get(code, 400),
        content={
            "code": code,
            "message": message or _DEFAULT_MESSAGE.get(code, "未知错误"),
            "data": data,
        },
    )
