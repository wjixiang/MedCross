"""应用配置。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from dotenv import load_dotenv

load_dotenv()

_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # apps/ukb-mcp/


class Settings(BaseSettings):
    """应用全局配置，从环境变量加载。"""

    dx_auth_token: str = Field(
        default="",
        alias="DX_AUTH_TOKEN",
        description="DNAnexus auth token。",
    )
    dx_project_context_id: str = Field(
        default="",
        alias="DX_PROJECT_CONTEXT_ID",
        description="默认 DNAnexus 项目 ID。",
    )
    dx_api_server_host: str = Field(
        default="api.dnanexus.com",
        alias="DX_API_SERVER_HOST",
    )
    dx_api_server_port: int = Field(
        default=443,
        alias="DX_API_SERVER_PORT",
    )
    dx_api_server_protocol: str = Field(
        default="https",
        alias="DX_API_SERVER_PROTOCOL",
    )
    server_host: str = Field(default="0.0.0.0", description="服务监听地址。")
    server_port: int = Field(default=8000, description="服务监听端口。")
    db_path: str = Field(
        default=".cache/db.duckdb",
        alias="DB_PATH",
    )
    cache_db_path: str = Field(
        default=".cache/dx_cache.duckdb",
        alias="CACHE_DB_PATH",
        description="DuckDB 缓存文件路径。",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def _resolve_cache_path(self) -> Settings:
        p = Path(self.cache_db_path)
        if not p.is_absolute():
            self.cache_db_path = str(_BASE_DIR / p)
        return self


@lru_cache
def get_settings() -> Settings:
    """获取全局 Settings 单例。"""
    return Settings()
