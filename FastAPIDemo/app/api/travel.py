"""行程模块路由。

端点清单（前缀 /api/travel）：
    GET    /travel         行程列表（分页）
    GET    /travel/{id}    行程详情
    PUT    /travel/{id}    更新行程（显式编辑）
    DELETE /travel/{id}    删除行程

行程由对话流程中 LLM 输出的 <plan>{...}</plan> JSON 解析生成，
此处提供查询、更新与删除接口。
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.response import success
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.travel import (
    TravelListResponse,
    TravelPlanListItem,
    TravelPlanResponse,
    TravelPlanUpdateRequest,
)
from app.services import travel_service

router = APIRouter(prefix="/travel", tags=["行程"])


@router.get("")
def list_plans(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询当前用户的行程列表。

    响应 data：{list, total}（list 不含 days_plan/luggage 大字段）
    """
    plans, total = travel_service.list_plans(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    response = TravelListResponse(
        list=[TravelPlanListItem.model_validate(p) for p in plans],
        total=total,
    )
    return success(response.model_dump())


@router.get("/{plan_id}")
def get_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取行程详情（含完整 days_plan 与 luggage）。

    响应 data：TravelPlanResponse
    """
    plan = travel_service.get_plan(db, user_id=current_user.id, plan_id=plan_id)
    return success(TravelPlanResponse.model_validate(plan).model_dump())


@router.put("/{plan_id}")
def update_plan(
    plan_id: int,
    body: TravelPlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新行程（全量覆盖可变字段，未传字段保留原值）。

    用于前端显式编辑某天行程后保存，或对话外的手动修改。

    请求体：TravelPlanUpdateRequest（所有字段可选）
    响应 data：TravelPlanResponse
    """
    plan = travel_service.update_plan(
        db,
        user_id=current_user.id,
        plan_id=plan_id,
        data=body.model_dump(exclude_unset=True),
    )
    return success(TravelPlanResponse.model_validate(plan).model_dump())


@router.delete("/{plan_id}")
def delete_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除行程（硬删除）。"""
    travel_service.delete_plan(db, user_id=current_user.id, plan_id=plan_id)
    return success()
