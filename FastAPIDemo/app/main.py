"""FastAPI 应用入口。

职责：
    - 创建 FastAPI 应用实例
    - 注册 CORS 中间件
    - 注册全局异常处理器
    - 挂载各业务路由（阶段2-5逐步添加）
    - 提供健康检查接口
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.conversations import router as conversations_router
from app.api.knowledge import router as knowledge_router
from app.api.travel import router as travel_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.response import success
from app.database import engine
from app.services import auth_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期钩子。

    启动时执行：
        - 根据 SUPER_ADMIN_PHONE 升级系统管理员角色
    关闭时执行：
        - 当前阶段无清理
    """
    # 启动：确保系统管理员角色已升级
    with Session(engine) as db:
        auth_service.ensure_super_admin(db)
    yield
    # 关闭


def create_app() -> FastAPI:
    """工厂函数：创建并配置 FastAPI 应用。"""
    app = FastAPI(
        title=settings.APP_NAME,
        description="旅游攻略生成 API - 对话式行程规划 + 知识库 RAG 检索",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS 中间件：允许前端跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册全局异常处理器
    register_exception_handlers(app)

    # 注册业务路由
    app.include_router(auth_router, prefix="/api")
    app.include_router(knowledge_router, prefix="/api")
    app.include_router(conversations_router, prefix="/api")
    app.include_router(travel_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")

    # 健康检查接口
    @app.get("/api/health", tags=["系统"])
    def health_check():
        """健康检查：返回服务状态。

        用于运维监控与前端启动时探测后端可用性。
        """
        return success({"status": "ok", "app": settings.APP_NAME})

    return app


# 全局 app 实例，供 uvicorn 启动
app = create_app()
