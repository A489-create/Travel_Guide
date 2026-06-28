"""SQLModel 基类与公共 Mixin。"""
from datetime import datetime

from sqlmodel import SQLModel, Field
from sqlalchemy import func


class TimestampMixin(SQLModel):
    """审计字段 Mixin：所有业务表共享 created_at / updated_at。

    - created_at: 创建时间，由数据库 server_default=now() 自动填充
    - updated_at: 更新时间，每次更新由数据库 onupdate=now() 自动更新
    """

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
        description="创建时间",
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": func.now(),
        },
        description="更新时间",
    )
