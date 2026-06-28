"""对话业务逻辑层（含 RAG 流程）。

职责：
    - CRUD：会话列表、创建、详情、删除
    - 消息发送：保存用户消息 → 解析行程参数 → 向量检索知识库 →
      拼接 system prompt + 知识上下文 + 对话历史 → 返回 LLM 消息列表
    - 消息收尾：保存 assistant 消息 → 解析 <plan> 结构化行程 → 创建 TravelPlan

RAG 流程（流程 A）：
    用户消息 → 提取 destination/days/budget/preferences
    → 向量化查询 → pgvector 检索 top K
    → 拼接 system + 知识上下文 + 历史 → DeepSeek chat_stream
    → 流式返回 → 收尾解析 <plan>

设计要点：
    - prepare_message 为 async（调用 embedding API）
    - RAG 失败时降级为无知识上下文，不阻断对话
    - assistant 历史消息中的 <plan> 块在送入 LLM 前剥离
"""
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Optional

from sqlmodel import Session, func, select

from app.config import settings
from app.core.exceptions import BizException
from app.core.response import BizCode
from app.models.conversation import Conversation
from app.models.knowledge import KnowledgeEntry
from app.models.message import Message
from app.models.travel_plan import TravelPlan
from app.services.llm.factory import EmbeddingFactory, LLMFactory
from app.services.llm.prompts import build_travel_messages

# 历史消息最大条数（限制 LLM 上下文长度）
_MAX_HISTORY = 10

# 默认会话标题
_DEFAULT_TITLE = "新对话"

# 标题最大长度
_TITLE_MAX_LEN = 20

# 偏好关键词词典（用于从用户消息中提取偏好）
_PREFERENCE_KEYWORDS = [
    "美食", "文化", "历史", "自然", "购物", "风景", "寺庙",
    "博物馆", "海滩", "登山", "夜生活", "亲子", "艺术", "建筑",
    "公园", "温泉", "滑雪", "潜水", "摄影", "徒步",
]

# 类型中文名映射
_TYPE_LABELS = {"attraction": "景点", "food": "美食", "tip": "避坑"}


# ===== 同步 CRUD =====


def list_conversations(
    db: Session,
    *,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Conversation], int]:
    """分页查询当前用户的会话列表。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        page: 页码，从 1 开始
        page_size: 每页条数

    Returns:
        (conversations, total) 二元组
    """
    stmt = select(Conversation).where(
        Conversation.user_id == user_id,
        Conversation.status == "active",
    )
    total = db.exec(select(func.count()).select_from(stmt.subquery())).one()

    stmt = stmt.order_by(Conversation.updated_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    conversations = list(db.exec(stmt).all())
    return conversations, total


def create_conversation(
    db: Session,
    *,
    user_id: int,
    title: str | None = None,
) -> Conversation:
    """创建新会话。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        title: 会话标题，None 时使用默认标题"新对话"

    Returns:
        创建的 Conversation 对象
    """
    conversation = Conversation(
        user_id=user_id,
        title=title.strip() if title else _DEFAULT_TITLE,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation_detail(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
) -> tuple[Conversation, list[Message]]:
    """获取会话详情（含消息列表）。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        conversation_id: 会话 ID

    Returns:
        (conversation, messages) 二元组

    Raises:
        BizException(CONV_NOT_FOUND): 会话不存在
        BizException(CONV_FORBIDDEN): 无权操作该会话
    """
    conversation = _get_owned_conversation(db, user_id, conversation_id)

    # 加载消息（按 id 升序）
    messages = list(
        db.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
        ).all()
    )
    return conversation, messages


def delete_conversation(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
) -> None:
    """删除会话（软删除：status=archived）。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        conversation_id: 会话 ID

    Raises:
        BizException(CONV_NOT_FOUND): 会话不存在
        BizException(CONV_FORBIDDEN): 无权操作该会话
    """
    conversation = _get_owned_conversation(db, user_id, conversation_id)
    conversation.status = "archived"
    db.add(conversation)
    db.commit()


# ===== 消息发送 + RAG 流程 =====


async def prepare_message(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    content: str,
) -> dict:
    """消息发送前置处理（async，含 embedding + 向量检索）。

    流程：
        1. 校验会话归属
        2. 保存用户消息
        3. 解析 destination/days/budget/preferences
        4. 检测是否为重大行程变更意图
           - 是：保存 pending_params 并返回 plan_action_required 标记
           - 否：强制覆盖更新会话字段（含标题自动生成）
        5. 向量化查询 + pgvector 检索知识库（失败降级）
        6. 加载对话历史（剥离 <plan> 块）
        7. 加载当前行程（迭代修改场景）
        8. 组装 LLM 消息列表

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        conversation_id: 会话 ID
        content: 用户消息内容

    Returns:
        dict: 正常生成时返回 {"messages": list[dict], "destination": str | None,
              "current_plan_id": int | None}；
              需要确认时返回 {"plan_action_required": True, "changes": dict,
              "pending_params": dict}。

    Raises:
        BizException(MSG_CONTENT_EMPTY): 消息内容为空
        BizException(CONV_NOT_FOUND): 会话不存在
        BizException(CONV_FORBIDDEN): 无权操作该会话
    """
    if not content.strip():
        raise BizException(BizCode.MSG_CONTENT_EMPTY)

    # 1. 校验会话归属
    conversation = _get_owned_conversation(db, user_id, conversation_id)

    # 2. 保存用户消息
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=content,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # 3. 解析行程参数
    parsed = _parse_travel_params(content)

    # 4. 若当前已有关联行程，检测是否为重大变更意图
    current_plan = None
    if conversation.current_plan_id:
        current_plan = db.get(TravelPlan, conversation.current_plan_id)
        if current_plan is None:
            # 清理指向已删除 plan 的脏 current_plan_id，避免后续逻辑依赖失效引用
            conversation.current_plan_id = None
            db.add(conversation)
            db.commit()

    changes = _detect_plan_change(conversation, current_plan, parsed)
    if changes and current_plan:
        # 保存待确认参数并中断正常生成流程
        # 用户未提及的字段（None/[]）用当前 plan 的原值填充，避免 LLM 误认为用户要清空
        base = current_plan if current_plan else conversation
        conversation.pending_params = {
            "destination": parsed["destination"] or getattr(base, "destination", None),
            "days": parsed["days"] if parsed["days"] is not None else getattr(base, "days", None),
            "budget": str(parsed["budget"]) if parsed["budget"] is not None else (
                str(base.budget) if getattr(base, "budget", None) is not None else None
            ),
            "preferences": parsed["preferences"] if parsed["preferences"] else (
                list(base.preferences) if getattr(base, "preferences", None) else []
            ),
            "raw_message": content,
        }
        db.add(conversation)
        db.commit()
        return {
            "plan_action_required": True,
            "changes": changes,
            "pending_params": conversation.pending_params,
        }

    # 5. 非重大变更或首次生成：强制用最新参数覆盖会话字段
    updated = _sync_conversation_params(conversation, parsed)

    # 首条消息自动生成标题
    if conversation.title == _DEFAULT_TITLE:
        conversation.title = content[:_TITLE_MAX_LEN] + (
            "..." if len(content) > _TITLE_MAX_LEN else ""
        )
        updated = True

    if updated:
        db.add(conversation)
        db.commit()

    # 6. RAG 检索（失败降级为空上下文）
    knowledge_context = ""
    if conversation.destination:
        try:
            knowledge_context = await _retrieve_knowledge(
                db,
                query=content,
                destination=conversation.destination,
                user_id=user_id,
            )
        except BizException:
            # embedding 或向量检索失败，降级为无知识上下文
            pass

    # 7. 加载对话历史（当前消息之前的 _MAX_HISTORY 条）
    history = _load_history(db, conversation_id, before_id=user_message.id)

    # 8. 加载当前行程（若有），用于 LLM 上下文（迭代修改场景）
    current_plan_data = None
    if conversation.current_plan_id:
        plan = db.get(TravelPlan, conversation.current_plan_id)
        if plan:
            current_plan_data = {
                "title": plan.title,
                "destination": plan.destination,
                "days": plan.days,
                "budget": float(plan.budget) if plan.budget else None,
                "preferences": plan.preferences,
                "days_plan": plan.days_plan,
                "luggage": plan.luggage,
            }

    # 9. 组装 LLM 消息列表
    messages = build_travel_messages(
        user_message=content,
        history=history,
        knowledge_context=knowledge_context,
        current_plan=current_plan_data,
    )

    return {
        "messages": messages,
        "destination": conversation.destination,
        "current_plan_id": conversation.current_plan_id,
    }


def finalize_message(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    full_text: str,
    destination: str | None = None,
    current_plan_id: int | None = None,
) -> int | None:
    """消息发送收尾处理（同步）。

    流程：
        1. 保存 assistant 消息（完整文本，含 <plan> 块）
        2. 尝试解析 <plan>{...}</plan> JSON
        3. 若解析成功：
           - current_plan_id 存在 → 更新现有 TravelPlan（迭代修改）
           - current_plan_id 为空 → 新建 TravelPlan，并写入 conversation.current_plan_id

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        conversation_id: 会话 ID
        full_text: LLM 完整响应文本
        destination: 目的地（用于 TravelPlan，优先使用解析值）
        current_plan_id: 当前生效的行程 ID。为 None 时新建行程；
            非空时更新该行程（迭代修改场景）。

    Returns:
        int | None: 操作的 TravelPlan ID，未生成行程时为 None
    """
    # 1. 保存 assistant 消息
    assistant_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=full_text,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    # 2. 尝试解析 <plan>
    plan_data = _extract_plan(full_text)
    if not plan_data:
        return None

    # 3. 读取会话最新参数，强制同步到 plan（防止 LLM 遗漏导致旧数据残留）
    conversation = db.get(Conversation, conversation_id)
    latest_params = {
        "destination": conversation.destination if conversation else destination,
        "days": conversation.days if conversation else None,
        "budget": conversation.budget if conversation else None,
        "preferences": conversation.preferences if conversation else None,
    }

    # 4. 根据 current_plan_id 分支：有则更新，无则新建
    if current_plan_id:
        # 迭代修改：更新现有行程
        plan = _update_plan_from_json(
            db,
            user_id=user_id,
            plan_id=current_plan_id,
            plan_data=plan_data,
            fallback_destination=destination,
            pending_params=latest_params,
        )
    else:
        # 首次生成：新建行程
        plan = _create_plan_from_json(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            plan_data=plan_data,
            fallback_destination=destination,
            pending_params=latest_params,
        )
        # 新建时同步 current_plan_id 到会话
        if plan and conversation:
            conversation.current_plan_id = plan.id
            db.add(conversation)
            db.commit()

    return plan.id if plan else None


async def apply_plan_action(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    action: Literal["update", "create"],
) -> dict:
    """处理用户确认后的行程保存动作。

    流程：
        1. 校验会话归属并读取 pending_params
        2. 用 pending_params 强制覆盖 conversation 元数据
        3. 根据新目的地做 RAG 检索
        4. 组装 LLM 消息并流式生成完整计划
        5. 解析 <plan> JSON
        6. 按 action 更新现有行程或新建行程
        7. 清空 pending_params

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        conversation_id: 会话 ID
        action: "update" 覆盖当前攻略，"create" 新建攻略

    Returns:
        dict: {"plan_id": int, "action": str}

    Raises:
        BizException(CONV_NOT_FOUND): 会话不存在
        BizException(CONV_FORBIDDEN): 无权操作该会话
        BizException(PARAMS_REQUIRED): 没有待确认的行程参数
        BizException(PLAN_NOT_FOUND): update 时当前行程不存在
    """
    conversation = _get_owned_conversation(db, user_id, conversation_id)

    pending = conversation.pending_params
    if not pending:
        raise BizException(BizCode.BAD_REQUEST, "没有待确认的行程参数")

    # 1. 用 pending_params 覆盖 conversation 元数据（强制清空 None 字段）
    parsed = {
        "destination": pending.get("destination"),
        "days": pending.get("days"),
        "budget": _safe_decimal(pending.get("budget")),
        "preferences": pending.get("preferences"),
    }
    _sync_conversation_params(conversation, parsed, force_clear=True)
    db.add(conversation)
    db.commit()

    # 2. RAG 检索（基于新目的地）
    knowledge_context = ""
    if conversation.destination:
        try:
            knowledge_context = await _retrieve_knowledge(
                db,
                query=pending.get("destination") or "",
                destination=conversation.destination,
                user_id=user_id,
            )
        except BizException:
            pass

    # 3. 加载历史并组装 prompt
    last_message_id = (
        db.exec(
            select(Message.id)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
        ).first()
    )
    history = _load_history(
        db,
        conversation_id,
        before_id=last_message_id if last_message_id else 0,
    )

    # 若 current_plan_id 指向已删除的行程，清理脏引用
    if conversation.current_plan_id:
        plan = db.get(TravelPlan, conversation.current_plan_id)
        if plan is None:
            conversation.current_plan_id = None
            db.add(conversation)
            db.commit()

    current_plan_data = None
    if conversation.current_plan_id:
        plan = db.get(TravelPlan, conversation.current_plan_id)
        current_plan_data = {
            "title": plan.title,
            "destination": plan.destination,
            "days": plan.days,
            "budget": float(plan.budget) if plan.budget else None,
            "preferences": plan.preferences,
            "days_plan": plan.days_plan,
            "luggage": plan.luggage,
        }

    # 构造明确的生成指令：包含已确认参数 + 用户修改意图，避免 LLM 追问
    confirmed_lines = []
    if pending.get("destination"):
        confirmed_lines.append(f"- 目的地：{pending['destination']}")
    if pending.get("days") is not None:
        confirmed_lines.append(f"- 天数：{pending['days']}天")
    if pending.get("budget") is not None:
        confirmed_lines.append(f"- 预算：{pending['budget']}元")
    if pending.get("preferences"):
        confirmed_lines.append(f"- 偏好：{'、'.join(pending['preferences'])}")
    instruction = "用户已确认以下行程参数，请直接基于这些参数生成完整行程规划，无需再追问：\n"
    instruction += "\n".join(confirmed_lines)
    if pending.get("raw_message"):
        instruction += f"\n用户的修改要求：{pending['raw_message']}"
    instruction += "\n请输出完整的自然语言描述和 <plan> JSON 块。"

    messages = build_travel_messages(
        user_message=instruction,
        history=history,
        knowledge_context=knowledge_context,
        current_plan=current_plan_data,
    )

    # 4. 调用 LLM 生成完整计划
    llm = LLMFactory.get_llm()
    full_response = ""
    async for chunk in llm.chat_stream(messages):
        full_response += chunk

    # 5. 解析 <plan> JSON
    plan_data = _extract_plan(full_response)
    if not plan_data:
        raise BizException(BizCode.LLM_PARSE_FAILED)

    # 6. 根据 action 保存行程
    if action == "update":
        if not conversation.current_plan_id:
            raise BizException(BizCode.PLAN_NOT_FOUND)
        plan = _update_plan_from_json(
            db,
            user_id=user_id,
            plan_id=conversation.current_plan_id,
            plan_data=plan_data,
            fallback_destination=conversation.destination,
            pending_params=parsed,
        )
    else:  # create
        plan = _create_plan_from_json(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            plan_data=plan_data,
            fallback_destination=conversation.destination,
            pending_params=parsed,
        )
        if plan:
            conversation.current_plan_id = plan.id

    # 7. 保存 assistant 消息（含 <plan> 块，便于历史追溯）
    assistant_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=full_response,
    )
    db.add(assistant_message)

    # 8. 清空 pending_params
    conversation.pending_params = None
    db.add(conversation)
    db.commit()

    return {"plan_id": plan.id, "action": action}


# ===== 内部辅助函数 =====


def _get_owned_conversation(
    db: Session,
    user_id: int,
    conversation_id: int,
) -> Conversation:
    """获取会话并校验归属（避免重复代码）。

    Raises:
        BizException(CONV_NOT_FOUND): 会话不存在或已归档
        BizException(CONV_FORBIDDEN): 无权操作该会话
    """
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.status == "archived":
        raise BizException(BizCode.CONV_NOT_FOUND)
    if conversation.user_id != user_id:
        raise BizException(BizCode.CONV_FORBIDDEN)
    return conversation


def _parse_travel_params(text: str) -> dict:
    """从用户消息中正则解析行程参数。

    支持的解析项：
        - destination: "去东京玩" / "目的地：东京" / "想去巴黎旅游"
        - days: "5天" / "3日"
        - budget: "预算1万" / "5000元" / "2千预算"
        - preferences: 关键词匹配（美食/文化/历史/...）

    Args:
        text: 用户消息文本

    Returns:
        dict: {"destination": str | None, "days": int | None,
               "budget": Decimal | None, "preferences": list[str]}
    """
    return {
        "destination": _parse_destination(text),
        "days": _parse_days(text),
        "budget": _parse_budget(text),
        "preferences": _parse_preferences(text),
    }


def _parse_destination(text: str) -> Optional[str]:
    """从文本中提取目的地。

    匹配模式：
        - "去东京玩" / "想去巴黎旅游" / "到北京旅行"
        - "目的地：东京"
    """
    patterns = [
        r"(?:想去|去|到)(.+?)(?:玩|旅游|旅行|游玩|观光)",
        r"目的地[:：\s]*(.+?)(?:[，,。.\s]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            dest = match.group(1).strip()
            # 清理常见前缀
            dest = re.sub(r"^(?:我|我们|要去|到|去)\s*", "", dest).strip()
            if dest and 1 <= len(dest) <= 20:
                return dest
    return None


def _parse_days(text: str) -> Optional[int]:
    """从文本中提取天数。匹配 "5天" / "3日" / "玩5天"。"""
    match = re.search(r"(\d+)\s*[天日]", text)
    if match:
        days = int(match.group(1))
        if 1 <= days <= 30:
            return days
    return None


def _parse_budget(text: str) -> Optional[Decimal]:
    """从文本中提取预算。

    支持单位：
        - "万" → × 10000（如 "1万" = 10000）
        - "千" → × 1000（如 "5千" = 5000）
        - "元" 或无单位 → 原值
    """
    # 优先匹配 "预算N万/千/元"
    match = re.search(r"预算[:：\s]*(\d+(?:\.\d+)?)\s*(万千|万|千|元)?", text)
    if not match:
        # 回退匹配 "N万/千/元" 独立数字
        match = re.search(r"(\d+(?:\.\d+)?)\s*(万千|万|千)\s*(?:预算|块)?", text)
    if not match:
        return None

    num = float(match.group(1))
    unit = match.group(2) or "元"

    if "万" in unit:
        return Decimal(str(num * 10000)).quantize(Decimal("0.01"))
    if "千" in unit:
        return Decimal(str(num * 1000)).quantize(Decimal("0.01"))
    return Decimal(str(num)).quantize(Decimal("0.01"))


def _parse_preferences(text: str) -> list[str]:
    """从文本中匹配偏好关键词。"""
    return [kw for kw in _PREFERENCE_KEYWORDS if kw in text]


def _detect_plan_change(
    conversation: Conversation,
    current_plan: TravelPlan | None,
    parsed: dict,
) -> dict | None:
    """检测用户本次消息是否构成重大行程变更意图。

    以当前生效的 TravelPlan 为基准（无则使用 conversation 字段），
    对比 parsed 中新解析出的参数。满足任一重大变更条件即返回变更摘要。

    重大变更规则：
        - destination 非空且与基准不同
        - days 非空且与基准不同
        - budget 非空且相对变化超过 20%，或基准非空而新值被清空
        - preferences 集合差异超过 50%（包含清空全部偏好）

    Args:
        conversation: 当前会话对象
        current_plan: 当前生效的 TravelPlan（可为 None）
        parsed: _parse_travel_params 解析结果

    Returns:
        dict | None: 存在重大变更时返回 {字段: {"old": ..., "new": ...}}，否则 None
    """
    # 优先以 TravelPlan 为基准；无则退化为 conversation 字段，避免脏 current_plan_id 导致漏检
    base = current_plan if current_plan else conversation
    if not base:
        return None

    changes: dict[str, dict] = {}

    old_destination = getattr(base, "destination", None)
    new_destination = parsed.get("destination")
    if new_destination and new_destination != old_destination:
        changes["destination"] = {"old": old_destination, "new": new_destination}

    old_days = getattr(base, "days", None)
    new_days = parsed.get("days")
    if new_days is not None and new_days != old_days:
        changes["days"] = {"old": old_days, "new": new_days}

    old_budget = getattr(base, "budget", None)
    new_budget = parsed.get("budget")
    # budget 为 None 表示用户未提及，不视为变更（避免"改为7天"误触发预算清空）
    if new_budget is not None and old_budget is not None and old_budget > 0:
        diff = abs(float(new_budget - old_budget) / float(old_budget))
        if diff > 0.2:
            changes["budget"] = {"old": float(old_budget), "new": float(new_budget)}
    elif new_budget is not None and old_budget is None:
        changes["budget"] = {"old": None, "new": float(new_budget)}

    old_preferences = set(getattr(base, "preferences", None) or [])
    new_preferences = set(parsed.get("preferences") or [])
    # preferences 为空表示用户未提及，不视为变更
    if new_preferences:
        union = old_preferences | new_preferences
        if union:
            diff_ratio = len(old_preferences ^ new_preferences) / len(union)
            if diff_ratio > 0.5:
                changes["preferences"] = {
                    "old": sorted(old_preferences),
                    "new": sorted(new_preferences),
                }

    return changes if changes else None


def _sync_conversation_params(
    conversation: Conversation, parsed: dict, force_clear: bool = False
) -> bool:
    """用解析出的最新参数覆盖会话字段。

    默认模式（force_clear=False）：仅当 parsed 字段非空时覆盖，None 视为"未提及"保留旧值。
    强制模式（force_clear=True）：parsed 中的 None 视为"显式清空"，用于 apply_plan_action
    场景，pending_params 是用户确认的完整意图，None 表示取消该字段。

    Args:
        conversation: 当前会话对象
        parsed: _parse_travel_params 解析结果或 pending_params 转换结果
        force_clear: 是否强制清空 None 字段（确认行程变更时使用）

    Returns:
        bool: 是否有字段被更新
    """
    updated = False

    dest = parsed.get("destination")
    if dest:
        conversation.destination = dest
        updated = True
    # destination 是核心字段，即使 force_clear 也不清空：
    # 用户说"增加深圳"时 destination 解析为 None，但应保留原目的地让 LLM 理解完整意图

    days = parsed.get("days")
    if days is not None:
        conversation.days = days
        updated = True
    elif force_clear and days is None:
        conversation.days = None
        updated = True

    budget = parsed.get("budget")
    if budget is not None:
        conversation.budget = budget
        updated = True
    elif force_clear and budget is None:
        conversation.budget = None
        updated = True

    prefs = parsed.get("preferences")
    if prefs is not None:
        conversation.preferences = prefs
        updated = True
    elif force_clear and prefs is None:
        conversation.preferences = None
        updated = True

    return updated


def _strip_plan_from_content(content: str) -> str:
    """从 assistant 消息内容中移除 <plan>...</plan> 块。

    用于清理送入 LLM 的历史消息，避免 JSON 干扰。
    """
    return re.sub(r"<plan>.*?</plan>", "", content, flags=re.DOTALL).strip()


def _extract_plan(full_response: str) -> Optional[dict]:
    """从 LLM 完整响应中提取 <plan> JSON 块。

    使用精确正则确保 <plan> 标签后紧跟 JSON 对象（{），避免误匹配
    文本中出现的 "<plan>块：" 等非 JSON 内容。

    Args:
        full_response: LLM 完整响应文本

    Returns:
        dict | None: 解析成功返回字典，否则 None
    """
    match = re.search(r"<plan>\s*(\{.*\})\s*</plan>", full_response, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None


def _load_history(
    db: Session,
    conversation_id: int,
    *,
    before_id: int,
) -> list[dict]:
    """加载对话历史（当前消息之前），格式化为 OpenAI 消息列表。

    - 限制最近 _MAX_HISTORY 条
    - assistant 消息剥离 <plan> 块
    - 按时间正序返回

    Args:
        db: 数据库会话
        conversation_id: 会话 ID
        before_id: 排除此 ID 及之后的消息

    Returns:
        list[dict]: OpenAI 格式消息列表
    """
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.id < before_id,
        )
        .order_by(Message.id.desc())
        .limit(_MAX_HISTORY)
    )
    recent = list(db.exec(stmt).all())
    recent.reverse()  # 转为正序

    history: list[dict] = []
    for msg in recent:
        if msg.role == "user":
            history.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            cleaned = _strip_plan_from_content(msg.content)
            if cleaned:  # 跳过空消息
                history.append({"role": "assistant", "content": cleaned})
    return history


async def _retrieve_knowledge(
    db: Session,
    *,
    query: str,
    destination: str,
    user_id: int,
) -> str:
    """RAG 检索：向量化查询 → pgvector 检索 → 格式化为上下文文本。

    检索范围：系统知识 + 当前用户个人知识。

    Args:
        db: 数据库会话
        query: 查询文本
        destination: 目的地过滤
        user_id: 当前用户 ID（用于检索其个人知识）

    Returns:
        str: 格式化的知识上下文文本，无检索结果时为空字符串

    Raises:
        BizException: embedding 或向量检索失败时向上抛出
    """
    # 延迟导入避免循环依赖
    from app.services.knowledge_service import search_entries

    entries = await search_entries(
        db,
        query=query,
        destination=destination,
        top_k=settings.RAG_TOP_K,
        user_id=user_id,
    )
    return _format_knowledge_context(entries)


def _format_knowledge_context(entries: list[KnowledgeEntry]) -> str:
    """将检索到的知识条目格式化为上下文文本。

    格式：
        【景点】东京塔
        摘要：东京的标志性建筑
        内容：东京塔是位于...

        ---

        【美食】一兰拉面
        ...
    """
    if not entries:
        return ""

    sections: list[str] = []
    for entry in entries:
        type_label = _TYPE_LABELS.get(entry.type, entry.type)
        summary = entry.summary or "无"
        section = (
            f"【{type_label}】{entry.title}\n"
            f"摘要：{summary}\n"
            f"内容：{entry.content}"
        )
        sections.append(section)

    return "\n\n---\n\n".join(sections)


def _safe_decimal(value: Any) -> Optional[Decimal]:
    """安全转换为 Decimal，失败返回 None。"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _create_plan_from_json(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    plan_data: dict,
    fallback_destination: str | None = None,
    pending_params: dict | None = None,
) -> Optional[TravelPlan]:
    """从解析的 <plan> JSON 创建 TravelPlan 记录。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        conversation_id: 会话 ID
        plan_data: 解析后的 plan 字典
        fallback_destination: 目的地回退值（plan 未含时使用）
        pending_params: 用户确认后的最新行程参数，优先于 plan_data

    Returns:
        TravelPlan | None: 创建成功返回对象，关键字段缺失返回 None
    """
    destination = (
        pending_params.get("destination")
        if pending_params and pending_params.get("destination")
        else plan_data.get("destination") or fallback_destination
    )
    if not destination:
        return None

    days = (
        pending_params.get("days")
        if pending_params and pending_params.get("days") is not None
        else plan_data.get("days")
    )
    if not isinstance(days, int) or days < 1:
        days = 1

    budget = (
        pending_params.get("budget")
        if pending_params and pending_params.get("budget") is not None
        else plan_data.get("budget")
    )
    preferences = (
        pending_params.get("preferences")
        if pending_params and pending_params.get("preferences") is not None
        else plan_data.get("preferences")
    )

    plan = TravelPlan(
        user_id=user_id,
        conversation_id=conversation_id,
        title=str(plan_data.get("title", "未命名行程"))[:200],
        destination=str(destination)[:100],
        days=days,
        budget=_safe_decimal(budget),
        preferences=preferences,
        days_plan=plan_data.get("days_plan"),
        luggage=plan_data.get("luggage"),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _update_plan_from_json(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    plan_data: dict,
    fallback_destination: str | None = None,
    pending_params: dict | None = None,
) -> Optional[TravelPlan]:
    """根据解析的 <plan> JSON 更新现有 TravelPlan。

    与 _create_plan_from_json 对应，用于 current_plan_id 存在的场景。
    关键元数据（destination/days/budget/preferences）优先使用 pending_params，
    确保用户最新意图生效；days_plan/luggage 使用 LLM 输出覆盖。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID（用于权限校验）
        plan_id: 待更新的行程 ID
        plan_data: 解析后的 plan 字典
        fallback_destination: 目的地回退值
        pending_params: 用户确认后的最新行程参数，优先于 plan_data

    Returns:
        TravelPlan | None: 行程不存在或无权操作返回 None
    """
    plan = db.get(TravelPlan, plan_id)
    if not plan or plan.user_id != user_id:
        return None

    destination = (
        pending_params.get("destination")
        if pending_params and pending_params.get("destination")
        else plan_data.get("destination") or fallback_destination or plan.destination
    )

    days = (
        pending_params.get("days")
        if pending_params and pending_params.get("days") is not None
        else plan_data.get("days")
    )
    if not isinstance(days, int) or days < 1:
        days = plan.days

    budget = (
        pending_params.get("budget")
        if pending_params and pending_params.get("budget") is not None
        else plan_data.get("budget")
    )
    preferences = (
        pending_params.get("preferences")
        if pending_params and pending_params.get("preferences") is not None
        else plan_data.get("preferences")
    )

    plan.title = str(plan_data.get("title", plan.title))[:200]
    plan.destination = str(destination)[:100]
    plan.days = days
    # pending_params 的 budget/preferences 为 None 时表示用户显式清空，需同步到 plan
    if pending_params and pending_params.get("budget") is None:
        plan.budget = None
    elif budget is not None:
        plan.budget = _safe_decimal(budget)
    if pending_params and pending_params.get("preferences") is None:
        plan.preferences = None
    elif preferences is not None:
        plan.preferences = preferences
    if plan_data.get("days_plan") is not None:
        plan.days_plan = plan_data.get("days_plan")
    if plan_data.get("luggage") is not None:
        plan.luggage = plan_data.get("luggage")

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def set_current_plan(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    plan_id: int,
) -> None:
    """设置会话的当前行程（用于在多个历史行程间切换）。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        conversation_id: 会话 ID
        plan_id: 行程 ID（必须属于当前用户）

    Raises:
        BizException(CONV_NOT_FOUND): 会话不存在
        BizException(CONV_FORBIDDEN): 无权操作该会话
        BizException(PLAN_NOT_FOUND): 行程不存在
        BizException(PLAN_FORBIDDEN): 无权操作该行程
    """
    conversation = _get_owned_conversation(db, user_id, conversation_id)
    plan = db.get(TravelPlan, plan_id)
    if not plan:
        raise BizException(BizCode.PLAN_NOT_FOUND)
    if plan.user_id != user_id:
        raise BizException(BizCode.PLAN_FORBIDDEN)
    conversation.current_plan_id = plan_id
    db.add(conversation)
    db.commit()
