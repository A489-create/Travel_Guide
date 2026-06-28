"""数据库连接与会话管理模块。

基于 SQLModel + SQLAlchemy 2.0 创建 PostgreSQL 引擎与 SessionLocal。
通过 get_db 依赖注入为每个请求提供独立 session。
"""
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# 创建 SQLAlchemy 引擎：连接 PostgreSQL
# pool_pre_ping=True 避免使用已断开的连接
# pool_recycle=3600 每小时回收连接，避免数据库 wait_timeout
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)

# 会话工厂：与 engine 绑定
SessionLocal = Session(engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求获取独立 session，请求结束自动关闭。

    用法：
        @app.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """开发期辅助方法：根据 SQLModel.metadata 直接建表（不推荐生产用，生产用 Alembic）。"""
    # 显式 import 以触发模型注册到 metadata
    # 此函数仅用于测试或快速初始化，正式迁移走 alembic
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
