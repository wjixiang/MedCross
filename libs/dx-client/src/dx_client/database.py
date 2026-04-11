"""DNAnexus 数据库操作服务。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol

import dxpy
import pandas as pd
from dxpy.exceptions import DXError as DxPyDXError

from .cache import CacheStatus, ICache
from .dx_exceptions import (
    DXDatabaseNotFoundError,
    translate_dx_error,
)
from .dx_models import (
    DXDatabaseClusterInfo,
    DXDatabaseInfo,
    DXDatabaseTable,
)

logger = logging.getLogger(__name__)


class IDatabaseContext(Protocol):
    """DatabaseService 对客户端的窄依赖协议。

    提供 find_dataset 方法供 DatabaseService 跨域调用。
    """

    def find_dataset(
        self,
        name_pattern: str = "app*.dataset",
        *,
        refresh: bool = False,
    ) -> tuple[str, str]: ...


class IDatabaseService(ABC):
    """数据库操作抽象接口。"""

    @abstractmethod
    def invalidate_cache(self) -> None:
        """清除缓存的 database ID。在项目切换时调用。"""

    @abstractmethod
    def list_databases(
        self,
        project_id: str,
        name_pattern: str | None = None,
        limit: int = 100,
        *,
        refresh: bool = False,
    ) -> list[DXDatabaseInfo]:
        """列出项目中的 database 数据对象。"""

    @abstractmethod
    def get_database(
        self,
        project_id: str,
        *,
        refresh: bool = False,
    ) -> DXDatabaseInfo:
        """获取项目的 database 数据对象详情。自动发现并缓存。"""

    @abstractmethod
    def describe_database_cluster(
        self,
        project_id: str,
        *,
        refresh: bool = False,
    ) -> DXDatabaseClusterInfo:
        """获取数据库集群描述信息。自动发现 database ID。"""

    @abstractmethod
    def get_database_schema(
        self,
        project_id: str,
        table_name: str | None = None,
        *,
        refresh: bool = False,
    ) -> list[DXDatabaseTable]:
        """查看数据库中可用的数据表。自动发现 database ID。

        UKB-RAP 的 database 为 dnax 类型（Parquet 存储），无 SQL schema。
        本方法通过 ``database_list_folder`` 浏览顶层目录结构来列出数据表。
        """


class DatabaseService(IDatabaseService):
    """数据库操作默认实现。

    Args:
        cache: 共享缓存实例。
        context: 客户端上下文，用于跨域调用 find_dataset / extract_fields。
    """

    def __init__(self, cache: ICache, context: IDatabaseContext) -> None:
        self._cache = cache
        self._context = context
        self._cached_database_id: str | None = None

    def invalidate_cache(self) -> None:
        self._cached_database_id = None

    @staticmethod
    def _resolve_name_mode(pattern: str) -> str:
        """根据模式内容自动选择 name_mode。"""
        if "*" in pattern or "?" in pattern:
            return "glob"
        return "regexp"

    def _handle_dx_error(self, e: DxPyDXError, context: str) -> None:
        """将 dxpy 异常转换为 DXClientError 层级。"""
        translate_dx_error(e, context)

    def _ensure_database_id(
        self, project_id: str, *, refresh: bool = False,
    ) -> str:
        """解析并缓存 database ID。refresh=True 时强制重新发现。"""
        if not refresh and self._cached_database_id is not None:
            return self._cached_database_id
        databases = self.list_databases(project_id, limit=1, refresh=refresh)
        if not databases:
            raise DXDatabaseNotFoundError(
                f"No database found in project '{project_id}'."
            )
        self._cached_database_id = databases[0].id
        return self._cached_database_id

    # ── 实现 ──────────────────────────────────────────────────────────

    def list_databases(
        self,
        project_id: str,
        name_pattern: str | None = None,
        limit: int = 100,
        *,
        refresh: bool = False,
    ) -> list[DXDatabaseInfo]:
        cache_key = f"databases:{project_id}:{name_pattern or ''}:{limit}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            kwargs: dict[str, Any] = {
                "classname": "database",
                "project": project_id,
                "describe": True,
                "limit": limit,
            }
            if name_pattern:
                kwargs["name"] = name_pattern
                kwargs["name_mode"] = self._resolve_name_mode(name_pattern)
            result = [
                DXDatabaseInfo.model_validate(r["describe"])
                for r in dxpy.find_data_objects(**kwargs)
            ]
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(e, "Failed to list databases")
            raise

    def get_database(
        self,
        project_id: str,
        *,
        refresh: bool = False,
    ) -> DXDatabaseInfo:
        database_id = self._ensure_database_id(project_id, refresh=refresh)
        cache_key = f"database:{database_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            result = DXDatabaseInfo.model_validate(dxpy.describe(database_id))
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to get database '{database_id}'")
            raise

    def describe_database_cluster(
        self,
        project_id: str,
        *,
        refresh: bool = False,
    ) -> DXDatabaseClusterInfo:
        database_id = self._ensure_database_id(project_id, refresh=refresh)
        cache_key = f"db_cluster:{database_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            raw = dxpy.api.database_describe(database_id)  # type: ignore[attr-defined]
            result = DXDatabaseClusterInfo.model_validate(raw)
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(
                e, f"Failed to describe database cluster '{database_id}'"
            )
            raise

    def get_database_schema(
        self,
        project_id: str,
        table_name: str | None = None,
        *,
        refresh: bool = False,
    ) -> list[DXDatabaseTable]:
        database_id = self._ensure_database_id(project_id, refresh=refresh)
        cache_key = f"db_schema:{database_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached_tables = self._cache.get(cache_key)
            if cached_tables is not None:
                if table_name:
                    return [t for t in cached_tables if t.name == table_name]
                return cached_tables

        try:
            resp = dxpy.api.database_list_folder(database_id, {})  # type: ignore
        except DxPyDXError as e:
            self._handle_dx_error(
                e, f"Failed to list folder for database '{database_id}'"
            )
            raise

        raw_entries: list[dict[str, Any]] = resp.get("results", [])
        tables: list[DXDatabaseTable] = []
        for entry in raw_entries:
            folder_path = entry.get("path", "")
            parts = folder_path.rstrip("/").split("/")
            tbl_name = parts[-1] if parts else folder_path

            if table_name and tbl_name != table_name:
                continue

            tables.append(DXDatabaseTable(name=tbl_name))

        if table_name and not tables:
            raise DXDatabaseNotFoundError(
                f"Table '{table_name}' not found in database '{database_id}'."
            )

        logger.info(
            "Database '%s' has %d tables%s",
            database_id,
            len(tables),
            f" (filtered by '{table_name}')" if table_name else "",
        )

        self._cache.set(cache_key, tables)
        return tables
