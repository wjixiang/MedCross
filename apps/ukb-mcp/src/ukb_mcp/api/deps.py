"""共享依赖注入。"""

from __future__ import annotations

from fastapi import Request

from dx_client import IDXClient


def get_dx_client(request: Request) -> IDXClient:
    """从 app.state 获取 IDXClient 实例。"""
    return request.app.state.dx_client
