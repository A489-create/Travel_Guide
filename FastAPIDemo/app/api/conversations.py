"""对话模块路由（含 SSE 流式接口）。

端点清单（前缀 /api/conversations）：
    GET    /conversations                会话列表（分页）
    POST   /conversations                创建会话
    GET    /conversations/{id}           会话详情（含消息列表）
    DELETE /conversations/{id}           删除会话（软删除）
    POST   /conversations/{id}/messages  发送消息（SSE 流式 RAG）
    PUT    /conversations/{id}/current-plan  设置会话的当前行程

SSE 事件格式（前端用 fetch + ReadableStream 消费）：
    data: {"content": "片"}          // 文本片段
    data: {"content": "段"}          // 文本片段
    data: {"done": true, "planId": 123}  // 流结束 + 行程ID
    data: {"error": true, "message": "...", "code": 20007}  // 错误
    data: {"actionRequired": true, "changes": {...}}  // 需要用户确认行程变更
"""
import json

from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session

from app.config import settings
from app.core.exceptions import BizException
from app.core.response import BizCode, success
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
    PlanActionRequest,
    SendMessageRequest,
    SetCurrentPlanRequest,
)
from app.services import conversation_service
from app.services.llm.factory import LLMFactory

router = APIRouter(prefix="/conversations", tags=["对话"])


@router.get("")
def list_conversations(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询当前用户的会话列表。

    响应 data：{list, total}
    """
    conversations, total = conversation_service.list_conversations(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    response = ConversationListResponse(
        list=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
    )
    return success(response.model_dump())


@router.post("")
def create_conversation(
    body: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建新会话。

    请求体：{title?}
    响应 data：ConversationResponse
    """
    conversation = conversation_service.create_conversation(
        db,
        user_id=current_user.id,
        title=body.title,
    )
    return success(ConversationResponse.model_validate(conversation).model_dump())


@router.get("/{conversation_id}")
def get_conversation_detail(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取会话详情（含消息列表）。

    响应 data：ConversationDetailResponse
    """
    conversation, messages = conversation_service.get_conversation_detail(
        db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    # 组装详情响应：会话基础字段 + 消息列表
    response_data = ConversationResponse.model_validate(conversation).model_dump()
    response_data["messages"] = [
        MessageResponse.model_validate(m).model_dump() for m in messages
    ]
    return success(response_data)


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除会话（软删除：status=archived）。"""
    conversation_service.delete_conversation(
        db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    return success()


@router.put("/{conversation_id}/current-plan")
def set_current_plan(
    conversation_id: int,
    body: SetCurrentPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """设置会话的当前行程（用于在多个历史行程间切换"当前编辑"的行程）。

    请求体：{"plan_id": 123}
    """
    conversation_service.set_current_plan(
        db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        plan_id=body.plan_id,
    )
    return success()


@router.post("/{conversation_id}/plan-action")
async def confirm_plan_action(
    conversation_id: int,
    body: PlanActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """确认行程变更保存方式。

    当发送消息检测到重大行程变更时，前端需调用此接口告知后端
    选择"update"（覆盖当前攻略）还是"create"（新建攻略）。

    请求体：{"action": "update" | "create"}
    响应：{"plan_id": 123, "action": "update"}
    """
    result = await conversation_service.apply_plan_action(
        db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        action=body.action,
    )
    return success(data=result)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: int,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发送消息（SSE 流式 RAG）。

    请求体：{content}
    响应：text/event-stream

    流程：
        1. 前置处理：保存用户消息 → 解析参数 → 检测重大变更 →
           RAG 检索 → 组装 LLM 消息
        2. 流式返回：调用 DeepSeek chat_stream，逐 chunk 推送
        3. 收尾处理：保存 assistant 消息 → 解析 <plan> → 创建 TravelPlan
        4. 若检测到重大行程变更，直接返回 actionRequired 事件，不调用 LLM
    """
    # 1. 前置处理（async：含 embedding + 向量检索）
    prepared = await conversation_service.prepare_message(
        db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        content=body.content,
    )

    # 1.5 重大行程变更：需要用户确认保存方式
    if prepared.get("plan_action_required"):
        async def action_required_generator():
            yield {
                "data": json.dumps(
                    {
                        "actionRequired": True,
                        "changes": prepared.get("changes"),
                        "pendingParams": prepared.get("pending_params"),
                    },
                    ensure_ascii=False,
                )
            }

        return EventSourceResponse(action_required_generator(), ping=15)

    llm = LLMFactory.get_llm()

    # 2. SSE 流式生成器
    async def event_generator():
        """SSE 事件生成器：流式返回 LLM 文本 + 收尾处理。"""
        full_response: list[str] = []

        try:
            async for chunk in llm.chat_stream(prepared["messages"]):
                full_response.append(chunk)
                yield {"data": json.dumps({"content": chunk}, ensure_ascii=False)}
        except BizException as exc:
            # LLM 调用失败：推送错误事件并终止
            yield {
                "data": json.dumps(
                    {"error": True, "message": exc.message, "code": exc.code},
                    ensure_ascii=False,
                )
            }
            return

        # 3. 收尾处理（保存 assistant 消息 + 解析 <plan>）
        full_text = "".join(full_response)
        plan_id = conversation_service.finalize_message(
            db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            full_text=full_text,
            destination=prepared.get("destination"),
            current_plan_id=prepared.get("current_plan_id"),
        )
        yield {
            "data": json.dumps(
                {"done": True, "planId": plan_id},
                ensure_ascii=False,
            )
        }

    # ping 参数保持连接活跃（防止代理超时断开）
    return EventSourceResponse(event_generator(), ping=15)
