"""DNAnexus 平台数据访问客户端。

封装 dxpy SDK，为上层 biomarker/cohort/association/export 服务
提供类型安全的统一数据访问接口。

Usage::

    from ukb_mcp.infra import DXClient

    with DXClient() as client:
        projects = client.list_projects(name_pattern="ukb*")
        client.set_project(projects[0].id)
        files = client.list_files(folder="/biomarkers")
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import dxpy
from dxpy import DXRecord
from dxpy.exceptions import DXAPIError as DxPyDXAPIError
from dxpy.exceptions import DXError as DxPyDXError

from .dx_exceptions import (
    DXAPIError,
    DXAuthError,
    DXClientError,
    DXConfigError,
    DXFileNotFoundError,
)
from .dx_models import (
    DXClientConfig,
    DXDataObject,
    DXFileInfo,
    DXProject,
    DXRecordInfo,
)

logger = logging.getLogger(__name__)


def _load_default_config() -> DXClientConfig:
    """从环境变量加载默认配置。"""
    return DXClientConfig(
        auth_token=os.getenv("DX_AUTH_TOKEN", ""),
        project_context_id=os.getenv("DX_PROJECT_CONTEXT_ID", ""),
    )


default_dx_client_config = _load_default_config()


class IDXClient(ABC):
    """DNAnexus 平台数据访问抽象接口。

    子类需实现所有标注为 ``@abstractmethod`` 的方法。
    通过 ``close()`` 释放底层资源，建议配合上下文管理器使用。
    """

    # ── 项目操作 ──────────────────────────────────────────────────────────

    @abstractmethod
    def list_projects(self, name_pattern: str | None = None) -> list[DXProject]:
        """列出有权限访问的项目。"""

    @abstractmethod
    def get_project(self, project_id: str) -> DXProject:
        """获取项目详情。"""

    @abstractmethod
    def set_project(self, project_id: str) -> None:
        """切换当前项目上下文。"""

    # ── 文件操作 ──────────────────────────────────────────────────────────

    @abstractmethod
    def list_files(
        self,
        folder: str | None = None,
        name_pattern: str | None = None,
        recurse: bool = False,
        limit: int = 100,
    ) -> list[DXFileInfo]:
        """列出当前项目中的文件。"""

    @abstractmethod
    def describe_file(self, file_id: str) -> DXFileInfo:
        """获取文件元数据。"""

    @abstractmethod
    def download_file(self, file_id: str, local_path: str | None = None) -> Path:
        """下载文件到本地路径。"""

    # ── 记录操作 ──────────────────────────────────────────────────────────

    @abstractmethod
    def list_records(
        self,
        folder: str | None = None,
        name_pattern: str | None = None,
        limit: int = 100,
    ) -> list[DXRecordInfo]:
        """列出当前项目中的记录。"""

    @abstractmethod
    def get_record(self, record_id: str) -> DXRecordInfo:
        """获取记录详情（含 details 内容）。"""

    # ── 通用搜索 ──────────────────────────────────────────────────────────

    @abstractmethod
    def find_data_objects(
        self,
        classname: str = "file",
        name_pattern: str | None = None,
        properties: dict[str, str] | None = None,
        limit: int = 100,
    ) -> list[DXDataObject]:
        """在当前项目中搜索数据对象。"""

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def close(self) -> None:
        """释放资源（dxpy 无需显式清理，空实现）。"""

    def __enter__(self) -> IDXClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class DXClient(IDXClient):
    """DNAnexus 平台数据访问客户端。

    Args:
        config: 客户端配置。为 None 时使用模块级默认配置（环境变量）。

    生命周期::

        client = DXClient(config)
        client.connect()                    # 启动时调用，初始化 dxpy 连接
        projects = client.list_projects()   # 正常使用
        client.disconnect()                 # 关闭时调用，清理状态
    """

    def __init__(self, config: DXClientConfig | None = None) -> None:
        self._config = config or default_dx_client_config
        self._current_project_id: str = ""
        self._initialized = False

    @property
    def is_connected(self) -> bool:
        return self._initialized

    @property
    def current_project_id(self) -> str:
        return self._current_project_id

    def connect(self) -> None:
        """初始化 dxpy security context，建立与 DNAnexus 平台的连接。

        应在应用启动时调用。重复调用为空操作。
        """
        if self._initialized:
            return

        if not self._config.auth_token:
            raise DXConfigError(
                "DNAnexus auth token is required. "
                "Set DX_AUTH_TOKEN environment variable or pass config.auth_token."
            )

        dxpy.set_security_context(
            {"auth_token_type": "Bearer", "auth_token": self._config.auth_token}
        )

        dxpy.set_api_server_info(
            host=self._config.api_server_host,
            port=self._config.api_server_port,
            protocol=self._config.api_server_protocol,
        )

        if self._config.project_context_id:
            dxpy.set_project_context(self._config.project_context_id)
            dxpy.set_workspace_id(self._config.project_context_id)
            self._current_project_id = self._config.project_context_id

        self._initialized = True
        logger.info(
            "Connected to DNAnexus at %s://%s:%d",
            self._config.api_server_protocol,
            self._config.api_server_host,
            self._config.api_server_port,
        )

    def disconnect(self) -> None:
        """断开与 DNAnexus 平台的连接，清理全局状态。"""
        if not self._initialized:
            return
        self._initialized = False
        self._current_project_id = ""
        logger.info("Disconnected from DNAnexus")

    def _ensure_connected(self) -> None:
        """断言已连接，未连接时抛出异常。"""
        if not self._initialized:
            raise DXConfigError(
                "DXClient is not connected. Call connect() first."
            )

    @staticmethod
    def _resolve_name_mode(pattern: str) -> str:
        """根据模式内容自动选择 name_mode。"""
        if "*" in pattern or "?" in pattern:
            return "glob"
        return "regexp"

    def _handle_dx_error(self, e: DxPyDXError, context: str) -> None:
        """将 dxpy 异常转换为 DXClientError 层级。"""
        if isinstance(e, DxPyDXAPIError):
            status_code = getattr(e, "status", 0)
            error_name = getattr(e, "name", "")
            msg = f"{context}: {e}"
            if status_code == 401 or "auth" in error_name.lower():
                raise DXAuthError(msg, dx_error=e) from e
            if status_code == 404 or "not found" in str(e).lower():
                raise DXFileNotFoundError(msg, dx_error=e) from e
            raise DXAPIError(
                msg, status_code=status_code, error_type=error_name, dx_error=e
            ) from e
        raise DXClientError(f"{context}: {e}", dx_error=e) from e

    def _require_project(self) -> str:
        """断言已设置项目上下文，返回 project_id。"""
        if not self._current_project_id:
            raise DXConfigError("No project context set. Call set_project() first.")
        return self._current_project_id

    # ═══════════════════════════════════════════════════════════════════════
    #  项目操作
    # ═══════════════════════════════════════════════════════════════════════

    def list_projects(self, name_pattern: str | None = None) -> list[DXProject]:
        self._ensure_connected()
        try:
            kwargs: dict[str, Any] = {"describe": True, "limit": 1000}
            if name_pattern:
                kwargs["name"] = name_pattern
                kwargs["name_mode"] = self._resolve_name_mode(name_pattern)
            return [DXProject.model_validate(r) for r in dxpy.find_projects(**kwargs)]
        except DxPyDXError as e:
            self._handle_dx_error(e, "Failed to list projects")
            raise  # unreachable

    def get_project(self, project_id: str) -> DXProject:
        self._ensure_connected()
        try:
            return DXProject.model_validate(dxpy.describe(project_id))
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to get project '{project_id}'")
            raise

    def set_project(self, project_id: str) -> None:
        self._ensure_connected()
        try:
            dxpy.set_project_context(project_id)
            dxpy.set_workspace_id(project_id)
            self._current_project_id = project_id
            logger.info("Switched project context to: %s", project_id)
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to set project '{project_id}'")
            raise

    # ═══════════════════════════════════════════════════════════════════════
    #  文件操作
    # ═══════════════════════════════════════════════════════════════════════

    def list_files(
        self,
        folder: str | None = None,
        name_pattern: str | None = None,
        recurse: bool = False,
        limit: int = 100,
    ) -> list[DXFileInfo]:
        self._ensure_connected()
        project = self._require_project()
        try:
            kwargs: dict[str, Any] = {
                "classname": "file",
                "project": project,
                "folder": folder or "/",
                "recurse": recurse,
                "describe": True,
                "limit": limit,
            }
            if name_pattern:
                kwargs["name"] = name_pattern
                kwargs["name_mode"] = self._resolve_name_mode(name_pattern)
            return [
                DXFileInfo.model_validate(r["describe"])
                for r in dxpy.find_data_objects(**kwargs)
            ]
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to list files in '{folder or '/'}'")
            raise

    def describe_file(self, file_id: str) -> DXFileInfo:
        self._ensure_connected()
        try:
            return DXFileInfo.model_validate(
                dxpy.describe(file_id, project=self._current_project_id or None)
            )
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to describe file '{file_id}'")
            raise

    def download_file(self, file_id: str, local_path: str | None = None) -> Path:
        self._ensure_connected()
        try:
            if local_path is None:
                desc: dict[str, Any] = dxpy.describe(  # type: ignore[assignment]
                    file_id, project=self._current_project_id or None
                )
                local_path = str(desc.get("name", file_id))

            dxpy.download_dxfile(
                file_id,
                filename=local_path,
                project=self._current_project_id or None,
                chunksize=100 * 1024 * 1024,
            )
            logger.info("Downloaded file '%s' to '%s'", file_id, local_path)
            return Path(local_path)
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to download file '{file_id}'")
            raise

    # ═══════════════════════════════════════════════════════════════════════
    #  记录操作
    # ═══════════════════════════════════════════════════════════════════════

    def list_records(
        self,
        folder: str | None = None,
        name_pattern: str | None = None,
        limit: int = 100,
    ) -> list[DXRecordInfo]:
        self._ensure_connected()
        project = self._require_project()
        try:
            kwargs: dict[str, Any] = {
                "classname": "record",
                "project": project,
                "folder": folder or "/",
                "describe": True,
                "limit": limit,
            }
            if name_pattern:
                kwargs["name"] = name_pattern
                kwargs["name_mode"] = self._resolve_name_mode(name_pattern)
            return [
                DXRecordInfo.model_validate(r["describe"])
                for r in dxpy.find_data_objects(**kwargs)
            ]
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to list records in '{folder or '/'}'")
            raise

    def get_record(self, record_id: str) -> DXRecordInfo:
        self._ensure_connected()
        try:
            record = DXRecord(record_id, project=self._current_project_id or None)
            desc = record.describe()
            details = record.get_details()
            model = DXRecordInfo.model_validate(desc)
            model.details = details  # type: ignore[attr-defined]
            return model
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to get record '{record_id}'")
            raise

    # ═══════════════════════════════════════════════════════════════════════
    #  通用搜索
    # ═══════════════════════════════════════════════════════════════════════

    def find_data_objects(
        self,
        classname: str = "file",
        name_pattern: str | None = None,
        properties: dict[str, str] | None = None,
        limit: int = 100,
    ) -> list[DXDataObject]:
        self._ensure_connected()
        project = self._require_project()
        try:
            kwargs: dict[str, Any] = {
                "classname": classname,
                "project": project,
                "describe": True,
                "limit": limit,
            }
            if name_pattern:
                kwargs["name"] = name_pattern
                kwargs["name_mode"] = self._resolve_name_mode(name_pattern)
            if properties:
                kwargs["properties"] = properties
            return [
                DXDataObject.model_validate(r["describe"])
                for r in dxpy.find_data_objects(**kwargs)
            ]
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to find data objects (class={classname})")
            raise
