"""应用配置。"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


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
    host: str = Field(default="127.0.0.1", description="服务监听地址。")
    port: int = Field(default=8000, description="服务监听端口。")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """获取全局 Settings 单例。"""
    return Settings()
