"""管理后台路由。

端点清单（前缀 /api/admin，全部需要管理员权限）：
    === 系统知识库管理 ===
    POST   /admin/knowledge/generate      生成系统知识（owner_id=NULL）
    GET    /admin/knowledge               系统知识列表（含已禁用）
    GET    /admin/knowledge/{id}          系统知识详情
    PATCH  /admin/knowledge/{id}          修改系统知识
    DELETE /admin/knowledge/{id}          删除系统知识（软删除）
    GET    /admin/knowledge/tasks/{id}    系统生成任务状态

    === 用户管理 ===
    GET    /admin/users                   用户列表（分页，支持关键词/角色/状态筛选）
    PATCH  /admin/users/{id}/role         修改用户角色
    PATCH  /admin/users/{id}/status       启用/禁用用户
    DELETE /admin/users/{id}              删除用户（硬删除+级联清理）
    GET    /admin/users/{id}/stats        用户统计
    POST   /admin/users/{id}/reset-password  重置用户密码

响应格式统一为 {code, message, data}。
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlmodel import Session

from app.core.response import success
from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.schemas.auth import (
    AdminResetPasswordRequest,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
)
from app.schemas.common import UserResponse
from app.schemas.knowledge import (
    KnowledgeEntryResponse,
    KnowledgeGenerateRequest,
    KnowledgeListResponse,
    KnowledgeTaskResponse,
    KnowledgeUpdateRequest,
)
from app.services import auth_service, knowledge_service

router = APIRouter(prefix="/admin", tags=["管理后台"])


# ===== 系统知识库管理 =====


@router.post("/knowledge/generate")
def generate_system_knowledge(
    body: KnowledgeGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """管理员触发系统知识库 AI 生成。

    管理员触发的生成任务入库后 owner_id=NULL（系统知识）。
    立即返回 taskId，后台异步执行。

    请求体：{destination, types?}
    响应 data：{taskId}
    """
    task = knowledge_service.create_task(
        db,
        destination=body.destination,
        types=body.types,
        triggered_by=admin.id,
    )
    background_tasks.add_task(_run_generation_safely, task.id)
    return success({"taskId": task.id})


@router.get("/knowledge")
def list_system_knowledge(
    destination: str | None = Query(default=None, description="目的地过滤"),
    type: str | None = Query(default=None, description="类型过滤"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员查询系统知识库列表（含已禁用条目）。"""
    entries, total = knowledge_service.list_entries(
        db,
        destination=destination,
        entry_type=type,
        page=page,
        page_size=page_size,
        scope="system",
        include_disabled=True,
    )
    response = KnowledgeListResponse(
        list=[KnowledgeEntryResponse.model_validate(e) for e in entries],
        total=total,
    )
    return success(response.model_dump())


@router.get("/knowledge/{entry_id}")
def get_system_knowledge(
    entry_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员查询系统知识条目详情（含已禁用）。"""
    entry = knowledge_service.get_entry(
        db,
        entry_id,
        is_admin=True,
        include_disabled=True,
    )
    return success(KnowledgeEntryResponse.model_validate(entry).model_dump())


@router.patch("/knowledge/{entry_id}")
async def update_system_knowledge(
    entry_id: int,
    body: KnowledgeUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """管理员修改系统知识条目（含启用/禁用、文本变更重算 embedding）。"""
    entry = await knowledge_service.update_entry(
        db,
        entry_id=entry_id,
        user_id=admin.id,
        is_admin=True,
        payload=body.model_dump(exclude_unset=True),
    )
    return success(KnowledgeEntryResponse.model_validate(entry).model_dump())


@router.delete("/knowledge/{entry_id}")
def delete_system_knowledge(
    entry_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """管理员删除系统知识条目（软删除 enabled=False）。"""
    knowledge_service.delete_entry(
        db,
        entry_id=entry_id,
        user_id=admin.id,
        is_admin=True,
    )
    return success()


@router.get("/knowledge/tasks/{task_id}")
def get_system_task(
    task_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """管理员查询生成任务状态。"""
    task = knowledge_service.get_task(db, task_id, user_id=admin.id, is_admin=True)
    return success(KnowledgeTaskResponse.model_validate(task).model_dump())


# ===== 用户管理 =====


@router.get("/users")
def list_users(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    keyword: str | None = Query(default=None, description="搜索关键词（用户名/姓名/手机号）"),
    role: str | None = Query(default=None, description="角色筛选：admin（含 super_admin） / user / super_admin"),
    is_active: bool | None = Query(default=None, description="启用状态筛选"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员分页查询所有用户，支持关键词/角色/状态筛选。

    响应 data：{list, total}
    """
    users, total = auth_service.list_users(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        role=role,
        is_active=is_active,
    )
    response = {
        "list": [UserResponse.model_validate(u).model_dump() for u in users],
        "total": total,
    }
    return success(response)


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    body: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """管理员/系统管理员修改用户角色（admin / user）。"""
    user = auth_service.update_user_role(
        db,
        target_user_id=user_id,
        role=body.role,
        operator_id=admin.id,
        operator_role=admin.role,
    )
    return success(UserResponse.model_validate(user).model_dump())


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    body: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """管理员/系统管理员启用/禁用用户账号。"""
    user = auth_service.update_user_status(
        db,
        target_user_id=user_id,
        is_active=body.is_active,
        operator_id=admin.id,
        operator_role=admin.role,
    )
    return success(UserResponse.model_validate(user).model_dump())


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """删除用户（硬删除 + 级联清理个人数据）。

    super_admin 可删除 admin 和 user；admin 仅可删除 user；
    任何人都不可删除 super_admin 和自己。
    """
    auth_service.delete_user(
        db,
        target_user_id=user_id,
        operator_id=admin.id,
        operator_role=admin.role,
    )
    return success()


@router.get("/users/{user_id}/stats")
def get_user_stats(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员查看用户统计信息（知识数/会话数/行程数/消息数）。"""
    stats = auth_service.get_user_stats(db, user_id=user_id)
    return success(stats)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    body: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """管理员/系统管理员重置用户密码，重置后用户需重新登录。"""
    auth_service.reset_user_password(
        db,
        target_user_id=user_id,
        new_password=body.new_password,
        operator_id=admin.id,
        operator_role=admin.role,
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
        print(f"[admin] 后台生成任务 {task_id} 异常: {exc}")  # noqa: T201
