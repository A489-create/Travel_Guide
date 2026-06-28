"""知识库模块路由（个人知识库管理 + 系统知识只读浏览）。

端点清单（前缀 /api/knowledge，全部需登录）：
    GET    /knowledge            条目列表（scope=system 浏览系统 / mine 我的知识）
    GET    /knowledge/{id}       条目详情（系统可读，个人仅本人）
    POST   /knowledge/search     向量语义检索（系统 + 我的个人）
    POST   /knowledge/generate   触发个人知识 AI 生成（owner_id=当前用户）
    GET    /knowledge/tasks/{id} 我的生成任务状态
    PATCH  /knowledge/{id}       修改我的知识条目
    DELETE /knowledge/{id}       删除我的知识条目（软删除）

响应格式统一为 {code, message, data}。
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlmodel import Session

from app.core.response import success
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeEntryResponse,
    KnowledgeGenerateRequest,
    KnowledgeListResponse,
    KnowledgeSearchRequest,
    KnowledgeTaskResponse,
    KnowledgeUpdateRequest,
)
from app.services import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.get("")
def list_entries(
    destination: str | None = Query(default=None, description="目的地过滤"),
    type: str | None = Query(default=None, description="类型过滤 attraction/food/tip"),
    scope: str = Query(default="mine", description="查询范围：system=系统知识 / mine=我的知识"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页查询知识库条目。

    scope=mine（默认）：当前用户的个人知识库
    scope=system：系统知识库（只读浏览）

    响应 data：{list, total}
    """
    entries, total = knowledge_service.list_entries(
        db,
        destination=destination,
        entry_type=type,
        page=page,
        page_size=page_size,
        user_id=current_user.id,
        scope=scope,
    )
    response = KnowledgeListResponse(
        list=[KnowledgeEntryResponse.model_validate(e) for e in entries],
        total=total,
    )
    return success(response.model_dump())


@router.get("/{entry_id}")
def get_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取条目详情（含权限校验）。

    系统条目：任意登录用户可读
    个人条目：仅本人可读

    响应 data：KnowledgeEntryResponse
    """
    entry = knowledge_service.get_entry(
        db,
        entry_id,
        user_id=current_user.id,
        is_admin=(current_user.role == "admin"),
    )
    return success(KnowledgeEntryResponse.model_validate(entry).model_dump())


@router.post("/search")
async def search_entries(
    body: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """向量语义检索（系统知识 + 当前用户个人知识）。

    请求体：{query, destination, type?, topK?}
    响应 data：list[KnowledgeEntryResponse]
    """
    entries = await knowledge_service.search_entries(
        db,
        query=body.query,
        destination=body.destination,
        entry_type=body.type,
        top_k=body.top_k,
        user_id=current_user.id,
    )
    response = [KnowledgeEntryResponse.model_validate(e) for e in entries]
    return success([item.model_dump() for item in response])


@router.post("/generate")
def generate(
    body: KnowledgeGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发个人知识库 AI 生成（需登录）。

    普通用户触发的生成任务入库后 owner_id=当前用户（个人知识）。
    管理员触发的生成任务入库后 owner_id=NULL（系统知识，建议使用 /api/admin/knowledge/generate）。
    立即创建任务并返回 taskId，后台异步执行。

    请求体：{destination, types?}
    响应 data：{taskId}
    """
    task = knowledge_service.create_task(
        db,
        destination=body.destination,
        types=body.types,
        triggered_by=current_user.id,
    )
    # 调度后台异步生成任务
    background_tasks.add_task(_run_generation_safely, task.id)
    return success({"taskId": task.id})


@router.get("/tasks/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询生成任务状态（仅触发者本人或管理员可见）。

    响应 data：KnowledgeTaskResponse
    """
    task = knowledge_service.get_task(
        db,
        task_id,
        user_id=current_user.id,
        is_admin=(current_user.role == "admin"),
    )
    return success(KnowledgeTaskResponse.model_validate(task).model_dump())


@router.patch("/{entry_id}")
async def update_entry(
    entry_id: int,
    body: KnowledgeUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改知识条目（仅本人或管理员可改）。

    文本字段变更后自动重新计算 embedding。

    请求体：{title?, content?, summary?, metadata?, enabled?}
    响应 data：KnowledgeEntryResponse
    """
    entry = await knowledge_service.update_entry(
        db,
        entry_id=entry_id,
        user_id=current_user.id,
        is_admin=(current_user.role == "admin"),
        payload=body.model_dump(exclude_unset=True),
    )
    return success(KnowledgeEntryResponse.model_validate(entry).model_dump())


@router.delete("/{entry_id}")
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除知识条目（软删除 enabled=False，仅本人或管理员可删）。"""
    knowledge_service.delete_entry(
        db,
        entry_id=entry_id,
        user_id=current_user.id,
        is_admin=(current_user.role == "admin"),
    )
    return success()


# ===== 后台任务辅助 =====


async def _run_generation_safely(task_id: int) -> None:
    """后台任务包装：捕获未预期异常，避免任务静默失败。

    Args:
        task_id: 任务 ID
    """
    try:
        await knowledge_service.run_generation(task_id)
    except Exception as exc:
        # 后台任务异常无法返回前端，仅打印日志
        print(f"[knowledge] 后台生成任务 {task_id} 异常: {exc}")  # noqa: T201
