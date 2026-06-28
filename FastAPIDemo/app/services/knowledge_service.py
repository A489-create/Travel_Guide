"""知识库业务逻辑层。

职责：
    - CRUD：条目列表（分页）、详情
    - 向量检索：将查询向量化 → pgvector cosine 检索 top K
    - AI 生成入库：后台任务，调用 LLM 生成内容 + Embedding 向量化后批量入库

设计要点：
    - 同步 DB 操作（SQLModel Session）+ 异步 LLM/Embedding 调用混合
    - generate_for_destination 为 async，由 BackgroundTasks 调度
    - 任务表记录进度，前端轮询查看
    - 单条入库失败不阻断整体流程，仅累计 failed 计数
"""
import asyncio
import json
import re
from datetime import datetime, timezone

from sqlmodel import Session, func, or_, select

from app.config import settings
from app.core.exceptions import BizException
from app.core.response import BizCode
from app.models.knowledge import KnowledgeEntry
from app.models.knowledge_task import KnowledgeGenerationTask
from app.models.user import User
from app.services.llm.factory import EmbeddingFactory, LLMFactory
from app.services.llm.prompts import build_knowledge_messages

# 支持的条目类型
_VALID_TYPES = ("attraction", "food", "tip")

# 每种类型默认生成的条目数
_PER_TYPE_COUNT = 5

# Embedding 文本拼接模板：标题 + 摘要 + 内容
_EMBED_TEXT_TEMPLATE = "{title}\n{summary}\n{content}"

# scope 合法值
_VALID_SCOPES = ("system", "mine", "all")


# ===== 同步 CRUD =====


def list_entries(
    db: Session,
    *,
    destination: str | None = None,
    entry_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    scope: str = "mine",
    include_disabled: bool = False,
) -> tuple[list[KnowledgeEntry], int]:
    """分页查询知识库条目。

    Args:
        db: 数据库会话
        destination: 目的地过滤（精确匹配），None 表示不过滤
        entry_type: 类型过滤，None 表示不过滤
        page: 页码，从 1 开始
        page_size: 每页条数
        user_id: 当前用户 ID（scope=mine 时必填）
        scope: 查询范围 system=系统知识 / mine=我的个人 / all=系统+我的（管理员）
        include_disabled: 是否包含已禁用条目（管理员视图）

    Returns:
        (entries, total) 二元组：当前页条目列表 + 总数

    Raises:
        BizException(KNOWLEDGE_TYPE_INVALID): entry_type 不在合法集合
        BizException(KNOWLEDGE_SCOPE_INVALID): scope 不在合法集合
    """
    if entry_type and entry_type not in _VALID_TYPES:
        raise BizException(BizCode.KNOWLEDGE_TYPE_INVALID)

    if scope not in _VALID_SCOPES:
        raise BizException(BizCode.KNOWLEDGE_SCOPE_INVALID)

    # 构造条件
    stmt = select(KnowledgeEntry)
    if not include_disabled:
        stmt = stmt.where(KnowledgeEntry.enabled == True)  # noqa: E712

    # scope 过滤
    if scope == "system":
        stmt = stmt.where(KnowledgeEntry.owner_id.is_(None))
    elif scope == "mine":
        if user_id is None:
            raise BizException(BizCode.KNOWLEDGE_SCOPE_INVALID, "scope=mine 需登录")
        stmt = stmt.where(KnowledgeEntry.owner_id == user_id)
    else:  # all: 系统知识 + 当前用户个人知识
        if user_id is None:
            stmt = stmt.where(KnowledgeEntry.owner_id.is_(None))
        else:
            stmt = stmt.where(
                or_(
                    KnowledgeEntry.owner_id.is_(None),
                    KnowledgeEntry.owner_id == user_id,
                )
            )

    if destination:
        stmt = stmt.where(KnowledgeEntry.destination == destination)
    if entry_type:
        stmt = stmt.where(KnowledgeEntry.type == entry_type)

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.exec(count_stmt).one()

    # 分页（按创建时间倒序）
    stmt = stmt.order_by(KnowledgeEntry.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    entries = list(db.exec(stmt).all())

    return entries, total


def get_entry(
    db: Session,
    entry_id: int,
    *,
    user_id: int | None = None,
    is_admin: bool = False,
    include_disabled: bool = False,
) -> KnowledgeEntry:
    """按 ID 查询条目详情（含权限校验）。

    Args:
        db: 数据库会话
        entry_id: 条目 ID
        user_id: 当前用户 ID
        is_admin: 是否管理员（管理员可读任意条目）
        include_disabled: 是否包含已禁用条目（管理员视图）

    Returns:
        KnowledgeEntry 对象

    Raises:
        BizException(KNOWLEDGE_NOT_FOUND): 条目不存在
        BizException(KNOWLEDGE_FORBIDDEN): 无权访问该条目
    """
    entry = db.get(KnowledgeEntry, entry_id)
    if not entry:
        raise BizException(BizCode.KNOWLEDGE_NOT_FOUND)

    # 非管理员视图下，已禁用条目视为不存在
    if not include_disabled and not entry.enabled:
        raise BizException(BizCode.KNOWLEDGE_NOT_FOUND)

    # 权限校验：系统知识所有人可读；个人知识仅本人或管理员可读
    if entry.owner_id is not None:
        if not is_admin and entry.owner_id != user_id:
            raise BizException(BizCode.KNOWLEDGE_FORBIDDEN)
    return entry


def create_task(
    db: Session,
    *,
    destination: str,
    types: list[str] | None = None,
    triggered_by: int | None = None,
) -> KnowledgeGenerationTask:
    """创建生成任务记录（status=pending）。

    Args:
        db: 数据库会话
        destination: 目的地名称
        types: 生成类型列表，None 时默认全部三种
        triggered_by: 任务触发者 ID，None 表示 CLI/系统

    Returns:
        创建的 KnowledgeGenerationTask 对象
    """
    if not destination.strip():
        raise BizException(BizCode.KNOWLEDGE_DEST_EMPTY)

    # 校验并规范化类型
    final_types = types if types else list(_VALID_TYPES)
    for t in final_types:
        if t not in _VALID_TYPES:
            raise BizException(BizCode.KNOWLEDGE_TYPE_INVALID)

    task = KnowledgeGenerationTask(
        destination=destination.strip(),
        types=final_types,
        status="pending",
        triggered_by=triggered_by,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(
    db: Session,
    task_id: int,
    *,
    user_id: int | None = None,
    is_admin: bool = False,
) -> KnowledgeGenerationTask:
    """按 ID 查询生成任务（含可见性校验）。

    Args:
        db: 数据库会话
        task_id: 任务 ID
        user_id: 当前用户 ID
        is_admin: 是否管理员

    Returns:
        KnowledgeGenerationTask 对象

    Raises:
        BizException(NOT_FOUND): 任务不存在
        BizException(FORBIDDEN): 无权查看该任务
    """
    task = db.get(KnowledgeGenerationTask, task_id)
    if not task:
        raise BizException(BizCode.NOT_FOUND, "生成任务不存在")

    # 可见性：触发者本人或管理员可见
    if not is_admin and task.triggered_by is not None and task.triggered_by != user_id:
        raise BizException(BizCode.FORBIDDEN, "无权查看该任务")
    return task


# ===== 向量语义检索 =====


async def search_entries(
    db: Session,
    *,
    query: str,
    destination: str,
    entry_type: str | None = None,
    top_k: int | None = None,
    user_id: int | None = None,
) -> list[KnowledgeEntry]:
    """向量语义检索：将 query 向量化后进行 pgvector cosine 检索。

    检索范围：系统知识（owner_id IS NULL）+ 当前用户个人知识（owner_id=user_id）。

    流程：
        1. 调用 SiliconFlow embedding API 将 query 向量化
        2. 按 destination + 归属过滤 + cosine 距离升序检索 top K

    Args:
        db: 数据库会话
        query: 检索文本
        destination: 目的地过滤
        entry_type: 类型过滤，None 表示不过滤
        top_k: 返回条目数，None 时使用 settings.RAG_TOP_K
        user_id: 当前用户 ID，None 时仅检索系统知识

    Returns:
        list[KnowledgeEntry]: 匹配的条目列表（按相似度降序）

    Raises:
        BizException(KNOWLEDGE_DEST_EMPTY): destination 为空
        BizException(VECTOR_SEARCH_FAILED): 数据库检索异常
    """
    if not destination.strip():
        raise BizException(BizCode.KNOWLEDGE_DEST_EMPTY)

    if entry_type and entry_type not in _VALID_TYPES:
        raise BizException(BizCode.KNOWLEDGE_TYPE_INVALID)

    final_top_k = top_k if top_k else settings.RAG_TOP_K

    # 1. 向量化查询文本
    embedding_client = EmbeddingFactory.get_embedding()
    try:
        vectors = await embedding_client.embed([query])
    except BizException:
        # embedding 调用失败，向上抛出
        raise
    query_vector = vectors[0]

    # 2. 构造 pgvector cosine 检索
    try:
        stmt = (
            select(KnowledgeEntry)
            .where(KnowledgeEntry.destination == destination)
            .where(KnowledgeEntry.enabled == True)  # noqa: E712
            .where(KnowledgeEntry.embedding.is_not(None))
        )
        # 归属过滤：系统知识 + 当前用户个人知识
        if user_id is None:
            stmt = stmt.where(KnowledgeEntry.owner_id.is_(None))
        else:
            stmt = stmt.where(
                or_(
                    KnowledgeEntry.owner_id.is_(None),
                    KnowledgeEntry.owner_id == user_id,
                )
            )
        if entry_type:
            stmt = stmt.where(KnowledgeEntry.type == entry_type)
        # cosine_distance 升序（距离越小越相似）
        stmt = stmt.order_by(
            KnowledgeEntry.embedding.cosine_distance(query_vector)
        ).limit(final_top_k)

        entries = list(db.exec(stmt).all())
    except Exception as exc:
        raise BizException(
            BizCode.VECTOR_SEARCH_FAILED,
            f"向量检索异常: {exc}",
        ) from exc

    return entries


# ===== AI 生成入库（后台任务） =====


async def _collect_stream(messages: list[dict]) -> str:
    """收集流式 LLM 响应为完整字符串。

    Args:
        messages: OpenAI 消息列表

    Returns:
        str: 完整响应文本
    """
    llm = LLMFactory.get_llm()
    chunks: list[str] = []
    async for chunk in llm.chat_stream(messages):
        chunks.append(chunk)
    return "".join(chunks)


def _extract_json_array(text: str) -> list[dict]:
    """从 LLM 响应中鲁棒地提取 JSON 数组。

    处理以下情形：
        1. 纯 JSON 数组
        2. 包裹在 ```json ... ``` 代码块中
        3. 前后带解释性文字

    Args:
        text: LLM 原始响应文本

    Returns:
        list[dict]: 解析出的条目字典列表

    Raises:
        BizException(LLM_PARSE_FAILED): 解析失败
    """
    cleaned = text.strip()

    # 移除 markdown 代码块包裹
    code_block = re.search(r"```(?:json)?\s*(.+?)\s*```", cleaned, re.DOTALL)
    if code_block:
        cleaned = code_block.group(1).strip()

    # 定位首尾方括号
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise BizException(
            BizCode.LLM_PARSE_FAILED,
            "LLM 响应未找到 JSON 数组",
        )

    json_str = cleaned[start : end + 1]
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise BizException(
            BizCode.LLM_PARSE_FAILED,
            f"JSON 解析失败: {exc}",
        ) from exc

    if not isinstance(parsed, list):
        raise BizException(
            BizCode.LLM_PARSE_FAILED,
            "LLM 响应不是 JSON 数组",
        )

    return [item for item in parsed if isinstance(item, dict)]


def _build_entry_text(entry_data: dict) -> str:
    """拼接条目文本用于 embedding 输入。

    使用 标题 + 摘要 + 内容 拼接，平衡检索质量与 token 用量。

    Args:
        entry_data: LLM 生成的单条条目字典

    Returns:
        str: 用于 embedding 的文本
    """
    title = entry_data.get("title", "")
    summary = entry_data.get("summary", "")
    content = entry_data.get("content", "")
    return _EMBED_TEXT_TEMPLATE.format(title=title, summary=summary, content=content)


async def generate_for_destination(db: Session, task_id: int) -> None:
    """后台执行知识库生成（异步）。

    流程：
        1. 标记任务为 running
        2. 对每个 type：调用 LLM 生成条目 → 解析 JSON → 批量 embedding → 入库
        3. 单条入库失败仅累计 failed 计数，不阻断整体
        4. 单类型失败跳过，继续下一个类型
        5. 完成后标记 completed（含错误信息时为 failed）

    Args:
        db: 数据库会话（由调用方创建并管理生命周期）
        task_id: 任务 ID
    """
    task = db.get(KnowledgeGenerationTask, task_id)
    if not task:
        return

    # 标记为运行中
    task.status = "running"
    db.add(task)
    db.commit()

    # 根据触发者角色确定入库归属：
    #   triggered_by 为 None（CLI/系统）→ 系统知识（owner_id=None）
    #   triggered_by 为管理员 → 系统知识（owner_id=None）
    #   triggered_by 为普通用户 → 个人知识（owner_id=triggered_by）
    owner_id: int | None = None
    if task.triggered_by is not None:
        trigger_user = db.get(User, task.triggered_by)
        if trigger_user and trigger_user.role == "user":
            owner_id = task.triggered_by

    embedding_client = EmbeddingFactory.get_embedding()

    try:
        for entry_type in task.types:
            # 1. LLM 生成内容
            messages = build_knowledge_messages(
                destination=task.destination,
                entry_type=entry_type,
                count=_PER_TYPE_COUNT,
            )
            try:
                full_response = await _collect_stream(messages)
            except BizException:
                # LLM 调用失败，跳过此类型
                continue

            # 2. 解析 JSON 数组
            try:
                entries_data = _extract_json_array(full_response)
            except BizException:
                # JSON 解析失败，跳过此类型
                continue

            # 累计计划总数
            task.total += len(entries_data)
            db.add(task)
            db.commit()

            if not entries_data:
                continue

            # 3. 批量 embedding
            texts = [_build_entry_text(e) for e in entries_data]
            try:
                vectors = await embedding_client.embed(texts)
            except BizException:
                # embedding 批量失败，全部计入 failed
                task.failed += len(entries_data)
                db.add(task)
                db.commit()
                continue

            # 4. 逐条入库
            for entry_data, vector in zip(entries_data, vectors):
                try:
                    entry = KnowledgeEntry(
                        type=entry_type,
                        title=entry_data.get("title", "")[:200],
                        destination=task.destination,
                        content=entry_data.get("content", ""),
                        summary=entry_data.get("summary"),
                        metadata_=entry_data.get("metadata"),
                        embedding=vector,
                        source="ai",
                        owner_id=owner_id,
                    )
                    db.add(entry)
                    db.commit()
                    task.success += 1
                except Exception:
                    # 单条入库失败回滚并累计
                    db.rollback()
                    task.failed += 1
                db.add(task)
                db.commit()

        # 全部类型处理完成
        task.status = "completed"
    except Exception as exc:
        # 未预期异常：标记失败并记录
        task.status = "failed"
        task.error_msg = str(exc)[:1000]
    finally:
        task.completed_at = datetime.now(timezone.utc)
        db.add(task)
        db.commit()


async def run_generation(task_id: int) -> None:
    """后台任务入口：创建独立 DB session 并执行生成。

    设计原因：
        FastAPI 的 Depends(get_db) 在请求响应后关闭 session，
        后台任务需自行创建独立 session。

    Args:
        task_id: 任务 ID
    """
    # 延迟导入避免循环依赖
    from app.database import engine

    with Session(engine) as db:
        await generate_for_destination(db, task_id)


# ===== 条目管理（更新/删除） =====


async def update_entry(
    db: Session,
    *,
    entry_id: int,
    user_id: int,
    is_admin: bool,
    payload: dict,
) -> KnowledgeEntry:
    """更新知识条目（含权限校验与 embedding 重算）。

    Args:
        db: 数据库会话
        entry_id: 条目 ID
        user_id: 当前用户 ID
        is_admin: 是否管理员
        payload: 更新字段字典（title/content/summary/metadata/enabled）

    Returns:
        更新后的 KnowledgeEntry 对象

    Raises:
        BizException(KNOWLEDGE_NOT_FOUND): 条目不存在
        BizException(KNOWLEDGE_FORBIDDEN): 无权操作
    """
    entry = get_entry(db, entry_id, user_id=user_id, is_admin=is_admin, include_disabled=True)

    # 权限校验：仅 owner 或管理员可修改
    if not is_admin and entry.owner_id != user_id:
        raise BizException(BizCode.KNOWLEDGE_FORBIDDEN)

    # 记录是否需要重算 embedding（title/content/summary 任一变更）
    need_reembed = False

    if payload.get("title") is not None:
        entry.title = payload["title"][:200]
        need_reembed = True
    if payload.get("content") is not None:
        entry.content = payload["content"]
        need_reembed = True
    if payload.get("summary") is not None:
        entry.summary = payload["summary"]
        need_reembed = True
    if payload.get("metadata") is not None:
        entry.metadata_ = payload["metadata"]
    if payload.get("enabled") is not None:
        entry.enabled = payload["enabled"]

    # 文本变更后重新计算 embedding
    if need_reembed:
        embedding_client = EmbeddingFactory.get_embedding()
        text = _build_entry_text({
            "title": entry.title,
            "summary": entry.summary or "",
            "content": entry.content,
        })
        try:
            vectors = await embedding_client.embed([text])
            entry.embedding = vectors[0]
        except BizException:
            # embedding 失败不阻断更新，保留旧向量
            pass

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def delete_entry(
    db: Session,
    *,
    entry_id: int,
    user_id: int,
    is_admin: bool,
) -> None:
    """软删除知识条目（设置 enabled=False）。

    Args:
        db: 数据库会话
        entry_id: 条目 ID
        user_id: 当前用户 ID
        is_admin: 是否管理员

    Raises:
        BizException(KNOWLEDGE_NOT_FOUND): 条目不存在
        BizException(KNOWLEDGE_FORBIDDEN): 无权操作
    """
    entry = get_entry(db, entry_id, user_id=user_id, is_admin=is_admin, include_disabled=True)

    # 权限校验：仅 owner 或管理员可删除
    if not is_admin and entry.owner_id != user_id:
        raise BizException(BizCode.KNOWLEDGE_FORBIDDEN)

    entry.enabled = False
    db.add(entry)
    db.commit()
