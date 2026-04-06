"""UK Biobank 数据服务 — FastAPI 入口。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from ukb_mcp.api.v1.router import v1_router
from ukb_mcp.config import Settings, get_settings
from dx_client import DXClient, DXClientConfig, DXConfigError, IDXClient
from dx_client.cache import DuckDBCache

logger = logging.getLogger(__name__)


class CacheStatusMiddleware(BaseHTTPMiddleware):
    """在每个 API 响应中注入 X-Cache-Status 头。"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        dx_client: IDXClient | None = getattr(
            request.app.state, "dx_client", None,
        )
        if dx_client is not None:
            response.headers["X-Cache-Status"] = dx_client.cache_status.value
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # ── 启动阶段 ──────────────────────────────────────────────────────
    dx_client = DXClient(
        config=DXClientConfig(
            auth_token=settings.dx_auth_token,
            project_context_id=settings.dx_project_context_id,
            api_server_host=settings.dx_api_server_host,
            api_server_port=settings.dx_api_server_port,
            api_server_protocol=settings.dx_api_server_protocol,
        ),
        cache=DuckDBCache(settings.cache_db_path),
    )

    try:
        dx_client.connect()
    except DXConfigError as e:
        logger.error("Failed to connect to DNAnexus: %s", e)
        raise

    app.state.dx_client = dx_client
    logger.info(
        "UK Biobank Data Service started on %s:%d (project: %s)",
        settings.server_host,
        settings.server_port,
        dx_client.current_project_id or "(not set)",
    )

    yield

    # ── 关闭阶段 ──────────────────────────────────────────────────────
    dx_client.disconnect()
    logger.info("UK Biobank Data Service stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """创建 FastAPI 应用实例。"""
    app = FastAPI(
        title="UK Biobank Data Service",
        description="RESTful API for UK Biobank biomarker data on DNAnexus",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(CacheStatusMiddleware)
    app.include_router(v1_router)

    @app.get("/health")
    def health_check() -> dict:
        dx_client: IDXClient | None = getattr(app.state, "dx_client", None)
        return {
            "status": "ok",
            "dx_connected": dx_client.is_connected if dx_client else False,
            "project": getattr(dx_client, "current_project_id", ""),
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "ukb_mcp.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
    )
