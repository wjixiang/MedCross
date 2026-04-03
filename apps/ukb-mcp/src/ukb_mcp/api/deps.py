"""共享依赖注入。"""

from __future__ import annotations

from fastapi import Request

from ukb_mcp.infra import DXClient


def get_dx_client(request: Request) -> DXClient:
    """从 app.state 获取 DXClient 单例。"""
    return request.app.state.dx_client
