"""认证业务逻辑层。

职责：
    - 注册：校验手机号唯一性，bcrypt 哈希密码后入库
    - 登录：验证凭据，签发 Access + Refresh Token 对，Refresh Token 哈希入库
    - 刷新：校验 Refresh Token 有效性，吊销旧 Token，签发新 Token 对
    - 登出：吊销当前用户所有有效 Refresh Token
    - 获取当前用户：按 ID 查询
    - 修改密码：校验旧密码，更新哈希

异常处理：
    - 业务错误抛出 BizException，由全局异常处理器转为统一响应
"""
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, func, or_, select

from app.config import settings
from app.core.exceptions import BizException
from app.core.response import BizCode
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
    verify_refresh_token,
)
from app.models.token import RefreshToken
from app.models.user import User


def _get_refresh_token_expiry() -> datetime:
    """计算 Refresh Token 的过期时间（UTC）。"""
    return datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )


def register(
    db: Session,
    *,
    phone: str,
    username: str,
    name: str,
    password: str,
) -> User:
    """用户注册。

    Args:
        db: 数据库会话
        phone: 手机号
        username: 用户名
        name: 显示名
        password: 明文密码

    Returns:
        创建的 User 对象（不含密码哈希的敏感信息由 schema 层过滤）

    Raises:
        BizException(PHONE_ALREADY_REGISTERED): 手机号已注册
    """
    # 检查手机号是否已注册
    existing = db.exec(
        select(User).where(User.phone == phone)
    ).first()
    if existing:
        raise BizException(BizCode.PHONE_ALREADY_REGISTERED)

    # 创建用户
    user = User(
        phone=phone,
        username=username,
        name=name,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(
    db: Session,
    *,
    phone: str,
    password: str,
) -> tuple[User, str, str]:
    """用户登录。

    Args:
        db: 数据库会话
        phone: 手机号
        password: 明文密码

    Returns:
        (User, access_token, refresh_token) 三元组

    Raises:
        BizException(LOGIN_FAILED): 手机号或密码错误（不区分用户不存在与密码错误）
    """
    user = db.exec(select(User).where(User.phone == phone)).first()
    if not user or not verify_password(password, user.password_hash):
        raise BizException(BizCode.LOGIN_FAILED)

    # 校验账号是否启用（封禁用户拒绝登录）
    if not user.is_active:
        raise BizException(BizCode.USER_DISABLED)

    # 签发令牌对
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # Refresh Token 哈希入库
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=_get_refresh_token_expiry(),
    ))
    db.commit()

    return user, access_token, refresh_token


def refresh_tokens(
    db: Session,
    *,
    refresh_token: str,
) -> tuple[str, str]:
    """使用 Refresh Token 换取新的 Access + Refresh Token 对。

    流程：
        1. 解码 JWT 获取 user_id
        2. 哈希后在数据库中查找记录
        3. 校验未吊销且未过期
        4. 吊销旧 Token
        5. 签发新 Token 对并入库

    Args:
        db: 数据库会话
        refresh_token: Refresh Token 字符串

    Returns:
        (new_access_token, new_refresh_token) 二元组

    Raises:
        BizException(REFRESH_TOKEN_INVALID): Token 无效、已吊销或已过期
    """
    # 1. 解码 JWT
    user_id = verify_refresh_token(refresh_token)
    if user_id is None:
        raise BizException(BizCode.REFRESH_TOKEN_INVALID)

    # 2. 查找数据库记录
    token_hash = hash_token(refresh_token)
    record = db.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()

    # 3. 校验有效性
    if not record or record.is_revoked:
        raise BizException(BizCode.REFRESH_TOKEN_INVALID)

    # 检查过期时间（数据库记录的 expires_at）
    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise BizException(BizCode.REFRESH_TOKEN_INVALID)

    # 检查用户是否已被禁用（封禁用户不可刷新令牌）
    user = get_user_by_id(db, user_id)
    if not user.is_active:
        raise BizException(BizCode.USER_DISABLED)

    # 4. 吊销旧 Token
    record.is_revoked = True
    db.add(record)

    # 5. 签发新 Token 对
    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)
    db.add(RefreshToken(
        user_id=user_id,
        token_hash=hash_token(new_refresh_token),
        expires_at=_get_refresh_token_expiry(),
    ))
    db.commit()

    return new_access_token, new_refresh_token


def logout(db: Session, *, user_id: int) -> None:
    """登出：吊销当前用户所有未吊销的 Refresh Token。

    Args:
        db: 数据库会话
        user_id: 当前登录用户 ID
    """
    active_tokens = db.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
    ).all()
    for token in active_tokens:
        token.is_revoked = True
        db.add(token)
    db.commit()


def get_user_by_id(db: Session, user_id: int) -> User:
    """按 ID 查询用户。

    Args:
        db: 数据库会话
        user_id: 用户 ID

    Returns:
        User 对象

    Raises:
        BizException(USER_NOT_FOUND): 用户不存在
    """
    user = db.get(User, user_id)
    if not user:
        raise BizException(BizCode.USER_NOT_FOUND)
    return user


def change_password(
    db: Session,
    *,
    user_id: int,
    old_password: str,
    new_password: str,
) -> None:
    """修改密码。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        old_password: 旧密码
        new_password: 新密码

    Raises:
        BizException(USER_NOT_FOUND): 用户不存在
        BizException(OLD_PASSWORD_WRONG): 旧密码不正确
    """
    user = get_user_by_id(db, user_id)
    if not verify_password(old_password, user.password_hash):
        raise BizException(BizCode.OLD_PASSWORD_WRONG)

    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()


# ===== 管理员功能 =====


def can_manage(operator: User, target: User) -> bool:
    """判断操作者是否可对目标用户执行管理操作（改角色/禁用/删除/重置密码）。

    权限规则：
        - super_admin 可管理 admin 和 user
        - admin 仅可管理 user
        - 任何人都不可管理 super_admin（含自己与他人），防止锁死
        - 不可操作自己（由调用方额外校验）

    Args:
        operator: 操作者用户
        target: 被操作的目标用户

    Returns:
        True 表示可管理
    """
    if target.role == "super_admin":
        return False
    if operator.role == "super_admin":
        return True
    if operator.role == "admin":
        return target.role == "user"
    return False


def ensure_super_admin(db: Session) -> None:
    """启动时根据 SUPER_ADMIN_PHONE 环境变量升级对应用户为 super_admin。

    若手机号为空或用户不存在，打印日志提示但不报错。

    Args:
        db: 数据库会话
    """
    phone = settings.SUPER_ADMIN_PHONE
    if not phone:
        print("[startup] SUPER_ADMIN_PHONE 未配置，跳过系统管理员升级")  # noqa: T201
        return

    user = db.exec(select(User).where(User.phone == phone)).first()
    if not user:
        print(f"[startup] 手机号 {phone} 的用户尚未注册，待注册后重启自动升级")  # noqa: T201
        return

    if user.role != "super_admin":
        user.role = "super_admin"
        db.add(user)
        db.commit()
        print(f"[startup] 已将用户 {user.username}({phone}) 升级为系统管理员")  # noqa: T201
    else:
        print(f"[startup] 用户 {user.username}({phone}) 已是系统管理员")  # noqa: T201


def register_admin(
    db: Session,
    *,
    phone: str,
    username: str,
    name: str,
    password: str,
    invite_code: str,
) -> User:
    """管理员注册（需邀请码）。

    Args:
        db: 数据库会话
        phone: 手机号
        username: 用户名
        name: 显示名
        password: 明文密码
        invite_code: 管理员邀请码

    Returns:
        创建的 admin 角色用户

    Raises:
        BizException(ADMIN_INVITE_CODE_INVALID): 邀请码错误
        BizException(PHONE_ALREADY_REGISTERED): 手机号已注册
    """
    # 校验邀请码
    if not settings.ADMIN_INVITE_CODE or invite_code != settings.ADMIN_INVITE_CODE:
        raise BizException(BizCode.ADMIN_INVITE_CODE_INVALID)

    # 校验手机号唯一性
    existing = db.exec(select(User).where(User.phone == phone)).first()
    if existing:
        raise BizException(BizCode.PHONE_ALREADY_REGISTERED)

    # 创建管理员用户
    user = User(
        phone=phone,
        username=username,
        name=name,
        password_hash=hash_password(password),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[User], int]:
    """分页查询所有用户（管理员用），支持关键词/角色/状态筛选。

    Args:
        db: 数据库会话
        page: 页码，从 1 开始
        page_size: 每页条数
        keyword: 搜索关键词（模糊匹配 username/name/phone）
        role: 角色筛选 admin / user
        is_active: 启用状态筛选 True/False

    Returns:
        (users, total) 二元组
    """
    stmt = select(User)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                User.username.ilike(pattern),
                User.name.ilike(pattern),
                User.phone.ilike(pattern),
            )
        )
    if role:
        # 「管理员」标签筛选时同时返回 admin 与 super_admin
        if role == "admin":
            stmt = stmt.where(User.role.in_(("admin", "super_admin")))
        else:
            stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    total = db.exec(select(func.count()).select_from(stmt.subquery())).one()
    stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    users = list(db.exec(stmt).all())
    return users, total


def update_user_role(
    db: Session,
    *,
    target_user_id: int,
    role: str,
    operator_id: int,
    operator_role: str = "admin",
) -> User:
    """修改用户角色（管理员/系统管理员用）。

    Args:
        db: 数据库会话
        target_user_id: 目标用户 ID
        role: 目标角色 admin / user（super_admin 不可通过 API 设置）
        operator_id: 操作者用户 ID（防止自我降权）
        operator_role: 操作者角色（admin / super_admin）

    Returns:
        更新后的 User 对象

    Raises:
        BizException(USER_NOT_FOUND): 目标用户不存在
        BizException(USER_ROLE_INVALID): role 值非法
        BizException(BAD_REQUEST): 不允许操作自己
        BizException(FORBIDDEN): 权限不足（如 admin 尝试操作其他 admin）
    """
    if role not in ("admin", "user"):
        raise BizException(BizCode.USER_ROLE_INVALID)

    # 不允许操作自己（防止自我降权导致无管理员）
    if target_user_id == operator_id:
        raise BizException(BizCode.BAD_REQUEST, "不允许修改自己的角色")

    user = get_user_by_id(db, target_user_id)

    # 构造操作者对象用于权限判断
    operator = User(id=operator_id, role=operator_role, phone="", username="", name="", password_hash="")
    if not can_manage(operator, user):
        raise BizException(BizCode.FORBIDDEN, "无权操作该用户角色")

    user.role = role
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_status(
    db: Session,
    *,
    target_user_id: int,
    is_active: bool,
    operator_id: int,
    operator_role: str = "admin",
) -> User:
    """启用/禁用用户（管理员/系统管理员用）。

    Args:
        db: 数据库会话
        target_user_id: 目标用户 ID
        is_active: 目标启用状态
        operator_id: 操作者用户 ID（防止封禁自己）
        operator_role: 操作者角色（admin / super_admin）

    Returns:
        更新后的 User 对象

    Raises:
        BizException(USER_NOT_FOUND): 目标用户不存在
        BizException(BAD_REQUEST): 不允许操作自己
        BizException(FORBIDDEN): 权限不足（如 admin 尝试禁用其他 admin）
    """
    # 不允许封禁自己
    if target_user_id == operator_id:
        raise BizException(BizCode.BAD_REQUEST, "不允许修改自己的启用状态")

    user = get_user_by_id(db, target_user_id)

    # 权限校验：super_admin 可禁用 admin；admin 不可禁用 admin；任何人都不可禁用 super_admin
    operator = User(id=operator_id, role=operator_role, phone="", username="", name="", password_hash="")
    if not can_manage(operator, user):
        raise BizException(BizCode.FORBIDDEN, "无权操作该用户状态")

    user.is_active = is_active

    # 禁用用户时吊销其所有有效的 Refresh Token，使其立即失去访问权限
    if not is_active:
        active_tokens = db.exec(
            select(RefreshToken).where(
                RefreshToken.user_id == target_user_id,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
        ).all()
        for token in active_tokens:
            token.is_revoked = True
            db.add(token)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_user_password(
    db: Session,
    *,
    target_user_id: int,
    new_password: str,
    operator_id: int,
    operator_role: str = "admin",
) -> None:
    """管理员/系统管理员重置用户密码。

    重置后吊销该用户所有有效的 Refresh Token，强制重新登录。

    Args:
        db: 数据库会话
        target_user_id: 目标用户 ID
        new_password: 新密码明文
        operator_id: 操作者用户 ID（防止重置自己密码）
        operator_role: 操作者角色（admin / super_admin）

    Raises:
        BizException(USER_NOT_FOUND): 目标用户不存在
        BizException(BAD_REQUEST): 不允许重置自己的密码
        BizException(FORBIDDEN): 权限不足
    """
    if target_user_id == operator_id:
        raise BizException(BizCode.BAD_REQUEST, "不允许重置自己的密码，请使用修改密码功能")

    user = get_user_by_id(db, target_user_id)

    operator = User(id=operator_id, role=operator_role, phone="", username="", name="", password_hash="")
    if not can_manage(operator, user):
        raise BizException(BizCode.FORBIDDEN, "无权重置该用户密码")

    user.password_hash = hash_password(new_password)
    db.add(user)

    # 吊销所有有效 Refresh Token，强制重新登录
    active_tokens = db.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == target_user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
    ).all()
    for token in active_tokens:
        token.is_revoked = True
        db.add(token)

    db.commit()


def get_user_stats(db: Session, *, user_id: int) -> dict:
    """查询用户统计信息（管理员用）。

    Args:
        db: 数据库会话
        user_id: 目标用户 ID

    Returns:
        统计字典：user_id/role/is_active/created_at + 各资源计数

    Raises:
        BizException(USER_NOT_FOUND): 用户不存在
    """
    # 延迟导入避免循环依赖
    from app.models.conversation import Conversation
    from app.models.knowledge import KnowledgeEntry
    from app.models.message import Message
    from app.models.travel_plan import TravelPlan

    user = get_user_by_id(db, user_id)

    # 个人知识条目数（owner_id=user_id）
    knowledge_count = db.exec(
        select(func.count()).where(KnowledgeEntry.owner_id == user_id)
    ).one()

    # 会话数
    conversation_count = db.exec(
        select(func.count()).where(Conversation.user_id == user_id)
    ).one()

    # 行程数
    travel_plan_count = db.exec(
        select(func.count()).where(TravelPlan.user_id == user_id)
    ).one()

    # 消息数（通过 conversation 关联用户）
    conv_ids_subq = select(Conversation.id).where(Conversation.user_id == user_id)
    message_count = db.exec(
        select(func.count()).where(Message.conversation_id.in_(conv_ids_subq))
    ).one()

    return {
        "user_id": user.id,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "knowledge_count": knowledge_count,
        "conversation_count": conversation_count,
        "travel_plan_count": travel_plan_count,
        "message_count": message_count,
    }


def delete_user(
    db: Session,
    *,
    target_user_id: int,
    operator_id: int,
    operator_role: str = "admin",
) -> None:
    """删除用户（硬删除 + 级联清理个人数据）。

    级联清理顺序：
        1. messages（通过 conversation 关联）
        2. travel_plans
        3. conversations
        4. knowledge_entries（个人知识，owner_id=target）
        5. knowledge_generation_tasks.triggered_by 置 NULL（保留任务历史）
        6. refresh_tokens
        7. users

    Args:
        db: 数据库会话
        target_user_id: 目标用户 ID
        operator_id: 操作者用户 ID（防止删除自己）
        operator_role: 操作者角色（admin / super_admin）

    Raises:
        BizException(USER_NOT_FOUND): 目标用户不存在
        BizException(BAD_REQUEST): 不允许删除自己
        BizException(FORBIDDEN): 权限不足（如 admin 尝试删除其他 admin）
    """
    # 延迟导入避免循环依赖
    from sqlalchemy import delete, update

    from app.models.conversation import Conversation
    from app.models.knowledge import KnowledgeEntry
    from app.models.knowledge_task import KnowledgeGenerationTask
    from app.models.message import Message
    from app.models.travel_plan import TravelPlan

    # 不允许删除自己
    if target_user_id == operator_id:
        raise BizException(BizCode.BAD_REQUEST, "不允许删除自己的账号")

    user = get_user_by_id(db, target_user_id)

    # 权限校验
    operator = User(id=operator_id, role=operator_role, phone="", username="", name="", password_hash="")
    if not can_manage(operator, user):
        raise BizException(BizCode.FORBIDDEN, "无权删除该用户")

    # 1. 收集该用户所有会话 ID
    conv_ids = list(db.exec(
        select(Conversation.id).where(Conversation.user_id == target_user_id)
    ).all())

    # 2. 删除会话下的所有消息
    if conv_ids:
        db.exec(delete(Message).where(Message.conversation_id.in_(conv_ids)))

    # 3. 删除行程攻略
    db.exec(delete(TravelPlan).where(TravelPlan.user_id == target_user_id))

    # 4. 删除会话
    db.exec(delete(Conversation).where(Conversation.user_id == target_user_id))

    # 5. 删除个人知识条目
    db.exec(delete(KnowledgeEntry).where(KnowledgeEntry.owner_id == target_user_id))

    # 6. 生成任务 triggered_by 置 NULL，保留历史记录
    db.exec(
        update(KnowledgeGenerationTask)
        .where(KnowledgeGenerationTask.triggered_by == target_user_id)
        .values(triggered_by=None)
    )

    # 7. 删除所有 Refresh Token
    db.exec(delete(RefreshToken).where(RefreshToken.user_id == target_user_id))

    # 8. 删除用户
    db.exec(delete(User).where(User.id == target_user_id))

    db.commit()
