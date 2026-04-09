"""DXClient 共享基础设施。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dxpy.exceptions import DXError as DxPyDXError

from .dx_exceptions import DXConfigError, translate_dx_error


class _ConnectedProjectMixin:
    """提供连接/项目守卫和工具方法的 Mixin。

    要求宿主类提供:
      - _initialized: bool
      - _current_project_id: str
    """

    def _ensure_connected(self) -> None:
        """断言已连接，未连接时抛出异常。"""
        if not self._initialized:  # type: ignore[attr-defined]
            raise DXConfigError("DXClient is not connected. Call connect() first.")

    def _require_project(self) -> str:
        """断言已设置项目上下文，返回 project_id。"""
        if not self._current_project_id:  # type: ignore[attr-defined]
            raise DXConfigError("No project context set. Call set_project() first.")
        return self._current_project_id  # type: ignore[attr-defined]

    @staticmethod
    def _resolve_name_mode(pattern: str) -> str:
        """根据模式内容自动选择 name_mode。"""
        if "*" in pattern or "?" in pattern:
            return "glob"
        return "regexp"

    @staticmethod
    def _handle_dx_error(e: DxPyDXError, context: str) -> None:
        """将 dxpy 异常转换为 DXClientError 层级。"""
        translate_dx_error(e, context)
