"""UK Biobank 数据服务 — FastAPI 入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1.router import v1_router
from config import Settings, get_settings
from infra import DXClient, DXClientConfig, DXConfigError

logger = logging.getLogger(__name__)


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
        )
    )

    try:
        dx_client.connect()
    except DXConfigError as e:
        logger.error("Failed to connect to DNAnexus: %s", e)
        raise

    app.state.dx_client = dx_client
    logger.info(
        "UK Biobank Data Service started on %s:%d (project: %s)",
        settings.host,
        settings.port,
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
    app.include_router(v1_router)

    @app.get("/health")
    def health_check() -> dict:
        dx_client: DXClient | None = getattr(app.state, "dx_client", None)
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
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
