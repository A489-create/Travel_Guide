"""Alembic 迁移环境配置。

从 app.config.settings 读取 DATABASE_URL，导入 SQLModel.metadata 供 autogenerate 使用，
并在执行迁移前启用 pgvector 扩展。

注意：不通过 config.set_main_option 注入 URL，因 configparser 的 % 插值会与
URL 编码的 % 冲突，改为直接用 settings.DATABASE_URL 创建 engine。
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import create_engine, pool, text
from sqlmodel import SQLModel

from alembic import context

# === 将项目根目录加入 sys.path，使 app.* 可导入 ===
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 导入配置与模型，触发 SQLModel.metadata 注册
from app.config import settings  # noqa: E402
import app.models  # noqa: E402, F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 使用 SQLModel.metadata 作为 autogenerate 的比对基准
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL 脚本，不连接数据库。

    先输出 pgvector 扩展创建语句，再执行迁移。
    """
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        # 启用 pgvector 扩展（幂等）
        context.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。

    直接用 settings.DATABASE_URL 创建 engine，避免 configparser % 插值冲突。
    先执行 CREATE EXTENSION 确保 pgvector 可用，再比对 metadata 执行迁移。
    """
    connectable = create_engine(settings.DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # 启用 pgvector 扩展（需 superuser/owner 权限，幂等语句）
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
