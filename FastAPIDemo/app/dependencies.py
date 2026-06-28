"""FastAPI 公共依赖。

提供 get_current_user 依赖，用于需要登录鉴权的路由。
"""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.core.exceptions import BizException
from app.core.response import BizCode
from app.core.security import verify_access_token
from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id

# OAuth2 Bearer Token 提取器，auto_error=False 以便自定义错误响应
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,
)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization Bearer Token 中解析当前登录用户。

    用法：
        @router.get("/me")
        def me(current_user: User = Depends(get_current_user)):
            ...

    Raises:
        BizException(UNAUTHORIZED): 未携带 Authorization 头
        BizException(TOKEN_INVALID): Token 无效或已过期
        BizException(USER_NOT_FOUND): 用户不存在（已删除）
        BizException(USER_DISABLED): 账号已被禁用
    """
    if not token:
        raise BizException(BizCode.UNAUTHORIZED)

    user_id = verify_access_token(token)
    if user_id is None:
        raise BizException(BizCode.TOKEN_INVALID)

    user = get_user_by_id(db, user_id)
    # 封禁用户的已签发 token 视为无效
    if not user.is_active:
        raise BizException(BizCode.USER_DISABLED)
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户为管理员（admin 或 super_admin），否则抛 FORBIDDEN。

    用法：
        @router.get("/admin/users")
        def list_users(_: User = Depends(require_admin)):
            ...
    """
    if current_user.role not in ("admin", "super_admin"):
        raise BizException(BizCode.FORBIDDEN, "需要管理员权限")
    return current_user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户为系统管理员（super_admin），否则抛 FORBIDDEN。

    用于仅限系统管理员操作的敏感接口。
    """
    if current_user.role != "super_admin":
        raise BizException(BizCode.FORBIDDEN, "需要系统管理员权限")
    return current_user
