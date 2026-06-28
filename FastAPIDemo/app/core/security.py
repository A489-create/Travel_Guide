"""安全工具模块：bcrypt 密码哈希 + JWT 令牌签发与校验。

设计要点：
    - 密码使用 bcrypt 哈希存储（不可逆），verify 时比对哈希
    - Access Token 短期有效（默认 30 分钟），用于 API 鉴权
    - Refresh Token 长期有效（默认 7 天），仅用于换取新 Access Token
    - Refresh Token 入库时存储 SHA256 哈希，非明文，防止数据库泄露后被利用
    - JWT payload 携带 sub（user_id）与 type（access/refresh）区分令牌用途
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import settings


# ===== 密码哈希 =====

def hash_password(password: str) -> str:
    """使用 bcrypt 对明文密码进行哈希。

    Args:
        password: 明文密码

    Returns:
        bcrypt 哈希字符串（含 salt，可直接存入数据库）
    """
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。

    Args:
        plain: 用户输入的明文密码
        hashed: 数据库中存储的 bcrypt 哈希

    Returns:
        True 表示密码正确，False 表示错误
    """
    return bcrypt.checkpw(
        plain.encode("utf-8"), hashed.encode("utf-8")
    )


# ===== JWT 令牌 =====

def _create_token(user_id: int, token_type: str, expires_delta: timedelta) -> str:
    """签发 JWT 令牌（内部通用方法）。

    Args:
        user_id: 用户 ID，作为 sub 声明
        token_type: 令牌类型 "access" 或 "refresh"
        expires_delta: 过期时间增量

    Returns:
        编码后的 JWT 字符串
    """
    expire = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type,
        "exp": expire,
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_access_token(user_id: int) -> str:
    """签发 Access Token（短期，用于 API 鉴权）。"""
    return _create_token(
        user_id,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> str:
    """签发 Refresh Token（长期，仅用于刷新 Access Token）。"""
    return _create_token(
        user_id,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """解码并验证 JWT 令牌。

    Args:
        token: JWT 字符串

    Returns:
        解码后的 payload 字典（含 sub、type、exp）

    Raises:
        JWTError: 令牌无效、过期或签名错误时抛出
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def verify_access_token(token: str) -> int | None:
    """校验 Access Token 并返回 user_id。

    Args:
        token: Access Token 字符串

    Returns:
        user_id（int），令牌无效时返回 None
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


def verify_refresh_token(token: str) -> int | None:
    """校验 Refresh Token 并返回 user_id。

    Args:
        token: Refresh Token 字符串

    Returns:
        user_id（int），令牌无效时返回 None
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            return None
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


# ===== Token 哈希（入库存储用） =====

def hash_token(token: str) -> str:
    """对 Refresh Token 计算 SHA256 哈希，用于入库比对。

    数据库仅存储哈希值，即使数据库泄露也无法直接使用 Refresh Token。

    Args:
        token: Refresh Token 明文

    Returns:
        SHA256 十六进制哈希字符串
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
