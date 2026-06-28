"""行程业务逻辑层。

职责：
    - 分页查询当前用户的行程列表
    - 行程详情查询
    - 删除行程

行程由对话流程中 LLM 输出的 <plan>{...}</plan> JSON 解析生成，
此处仅提供查询与删除接口（创建逻辑在 conversation_service 中）。
"""
from sqlmodel import Session, func, select

from app.core.exceptions import BizException
from app.core.response import BizCode
from app.models.travel_plan import TravelPlan


def list_plans(
    db: Session,
    *,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[TravelPlan], int]:
    """分页查询当前用户的行程列表。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        page: 页码，从 1 开始
        page_size: 每页条数

    Returns:
        (plans, total) 二元组
    """
    stmt = select(TravelPlan).where(TravelPlan.user_id == user_id)
    total = db.exec(select(func.count()).select_from(stmt.subquery())).one()

    stmt = stmt.order_by(TravelPlan.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    plans = list(db.exec(stmt).all())
    return plans, total


def get_plan(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
) -> TravelPlan:
    """查询行程详情。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        plan_id: 行程 ID

    Returns:
        TravelPlan 对象

    Raises:
        BizException(PLAN_NOT_FOUND): 行程不存在
        BizException(PLAN_FORBIDDEN): 无权操作该行程
    """
    plan = db.get(TravelPlan, plan_id)
    if not plan:
        raise BizException(BizCode.PLAN_NOT_FOUND)
    if plan.user_id != user_id:
        raise BizException(BizCode.PLAN_FORBIDDEN)
    return plan


def delete_plan(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
) -> None:
    """删除行程（硬删除）。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        plan_id: 行程 ID

    Raises:
        BizException(PLAN_NOT_FOUND): 行程不存在
        BizException(PLAN_FORBIDDEN): 无权操作该行程
    """
    plan = get_plan(db, user_id=user_id, plan_id=plan_id)
    db.delete(plan)
    db.commit()


def update_plan(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    data: dict,
) -> TravelPlan:
    """更新行程可变字段（title/days/budget/preferences/days_plan/luggage）。

    用于 PUT /api/travel/{id} 显式更新接口。仅更新 data 中提供的字段。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        plan_id: 行程 ID
        data: 待更新的字段字典（已 exclude_unset 过滤）

    Returns:
        TravelPlan: 更新后的行程对象

    Raises:
        BizException(PLAN_NOT_FOUND): 行程不存在
        BizException(PLAN_FORBIDDEN): 无权操作该行程
    """
    plan = get_plan(db, user_id=user_id, plan_id=plan_id)
    for field in ("title", "days", "budget", "preferences", "days_plan", "luggage"):
        if field in data and data[field] is not None:
            setattr(plan, field, data[field])
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan
