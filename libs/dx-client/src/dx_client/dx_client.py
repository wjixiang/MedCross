"""DNAnexus 平台数据访问客户端。

封装 dxpy SDK，提供类型安全的统一数据访问接口。
通过 ``ICache`` 依赖注入实现可插拔的缓存策略。

所有数据读取方法默认命中缓存，传入 ``refresh=True`` 可强制从云端刷新。

Usage::

    from dx_client import DXClient, MemoryCache

    with DXClient(cache=MemoryCache()) as client:
        projects = client.list_projects(name_pattern="ukb*")
        client.set_project(projects[0].id)
        files = client.list_files(folder="/biomarkers")
"""

from __future__ import annotations

import glob
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, List

import dxpy
import pandas as pd
from dxpy import DXRecord
from dxpy.exceptions import DXAPIError as DxPyDXAPIError
from dxpy.exceptions import DXError as DxPyDXError

from .cache import CacheStatus, ICache, MemoryCache
from .dx_exceptions import (
    DXAPIError,
    DXAuthError,
    DXClientError,
    DXCohortError,
    DXConfigError,
    DXDatabaseNotFoundError,
    DXFileNotFoundError,
    DXJobError,
)
from .dx_models import (
    DXClientConfig,
    DXCohortInfo,
    DXDatabaseClusterInfo,
    DXDatabaseInfo,
    DXDatabaseTable,
    DXDataObject,
    DXFileInfo,
    DXJobInfo,
    DXProject,
    DXRecordInfo,
)
from .interfaces import IDXClient

logger = logging.getLogger(__name__)


def _load_default_config() -> DXClientConfig:
    """从环境变量加载默认配置。"""
    return DXClientConfig(
        auth_token=os.getenv("DX_AUTH_TOKEN", ""),
        project_context_id=os.getenv("DX_PROJECT_CONTEXT_ID", ""),
    )


default_dx_client_config = _load_default_config()


class DXClient(IDXClient):
    """DNAnexus 平台数据访问客户端。Use dxpy python SDK.

    Args:
        config: 客户端配置。为 None 时使用模块级默认配置（环境变量）。
        cache: 缓存实例。为 None 时使用 MemoryCache。

    生命周期::

        client = DXClient(config)
        client.connect()                    # 启动时调用，初始化 dxpy 连接
        projects = client.list_projects()   # 正常使用
        client.disconnect()                 # 关闭时调用，清理状态
    """

    def __init__(
        self,
        config: DXClientConfig | None = None,
        cache: ICache | None = None,
    ) -> None:
        self._config = config or default_dx_client_config
        self._cache: ICache = cache or MemoryCache()
        self._current_project_id: str = ""
        self._initialized = False
        self._cached_dataset_ref: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._initialized

    @property
    def current_project_id(self) -> str:
        return self._current_project_id

    @property
    def cache_status(self) -> CacheStatus:
        """最近一次数据读取的缓存状态。"""
        return self._cache.last_status

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
            raise DXConfigError("DXClient is not connected. Call connect() first.")

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

    def list_projects(
        self,
        name_pattern: str | None = None,
        *,
        refresh: bool = False,
    ) -> list[DXProject]:
        self._ensure_connected()
        cache_key = f"projects:{name_pattern or '*'}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            kwargs: dict[str, Any] = {"describe": True, "limit": 1000}
            if name_pattern:
                kwargs["name"] = name_pattern
                kwargs["name_mode"] = self._resolve_name_mode(name_pattern)
            result = [DXProject.model_validate(r) for r in dxpy.find_projects(**kwargs)]
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(e, "Failed to list projects")
            raise  # unreachable

    def get_project(
        self,
        project_id: str,
        *,
        refresh: bool = False,
    ) -> DXProject:
        self._ensure_connected()
        cache_key = f"project:{project_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            result = DXProject.model_validate(dxpy.describe(project_id))
            self._cache.set(cache_key, result)
            return result
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
        *,
        refresh: bool = False,
    ) -> list[DXFileInfo]:
        self._ensure_connected()
        project = self._require_project()
        cache_key = (
            f"files:{project}:{folder or '/'}:{name_pattern or ''}:{recurse}:{limit}"
        )
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
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
            result = [
                DXFileInfo.model_validate(r["describe"])
                for r in dxpy.find_data_objects(**kwargs)
            ]
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to list files in '{folder or '/'}'")
            raise

    def describe_file(
        self,
        file_id: str,
        *,
        refresh: bool = False,
    ) -> DXFileInfo:
        self._ensure_connected()
        cache_key = f"file:{file_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            result = DXFileInfo.model_validate(
                dxpy.describe(file_id, project=self._current_project_id or None)
            )
            self._cache.set(cache_key, result)
            return result
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
        *,
        refresh: bool = False,
    ) -> list[DXRecordInfo]:
        self._ensure_connected()
        project = self._require_project()
        cache_key = f"records:{project}:{folder or '/'}:{name_pattern or ''}:{limit}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
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
            result = [
                DXRecordInfo.model_validate(r["describe"])
                for r in dxpy.find_data_objects(**kwargs)
            ]
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to list records in '{folder or '/'}'")
            raise

    def get_record(
        self,
        record_id: str,
        *,
        refresh: bool = False,
    ) -> DXRecordInfo:
        self._ensure_connected()
        cache_key = f"record:{record_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            record = DXRecord(record_id, project=self._current_project_id or None)
            desc = record.describe()
            details = record.get_details()
            model = DXRecordInfo.model_validate(desc)
            model.details = details  # type: ignore[attr-defined]
            self._cache.set(cache_key, model)
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
        *,
        refresh: bool = False,
    ) -> list[DXDataObject]:
        self._ensure_connected()
        project = self._require_project()
        props_str = json.dumps(properties, sort_keys=True) if properties else ""
        cache_key = f"find_objects:{project}:{classname}:{name_pattern or ''}:{props_str}:{limit}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
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
            result = [
                DXDataObject.model_validate(r["describe"])
                for r in dxpy.find_data_objects(**kwargs)
            ]
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to find data objects (class={classname})")
            raise

    # ═══════════════════════════════════════════════════════════════════════
    #  数据库操作
    # ═══════════════════════════════════════════════════════════════════════

    def list_databases(
        self,
        name_pattern: str | None = None,
        limit: int = 100,
        *,
        refresh: bool = False,
    ) -> list[DXDatabaseInfo]:
        """列出当前项目中的 database 数据对象。"""
        self._ensure_connected()
        project = self._require_project()
        cache_key = f"databases:{project}:{name_pattern or ''}:{limit}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            kwargs: dict[str, Any] = {
                "classname": "database",
                "project": project,
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
        database_id: str,
        *,
        refresh: bool = False,
    ) -> DXDatabaseInfo:
        """获取 database 数据对象详情。"""
        self._ensure_connected()
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

    def find_database(
        self,
        name_pattern: str | None = None,
        *,
        refresh: bool = False,
    ) -> DXDatabaseInfo:
        """在当前项目中查找 database 数据对象。

        若 *name_pattern* 为 None，返回项目中第一个 database。
        """
        databases = self.list_databases(
            name_pattern=name_pattern, limit=10, refresh=refresh
        )
        if not databases:
            project_id = self._require_project()
            detail = f" Matching pattern: '{name_pattern}'" if name_pattern else ""
            raise DXDatabaseNotFoundError(
                f"No database found in project '{project_id}'.{detail}"
            )
        return databases[0]

    def describe_database_cluster(
        self,
        db_cluster_id: str,
        *,
        refresh: bool = False,
    ) -> DXDatabaseClusterInfo:
        """获取数据库集群描述信息。

        Returns:
            DXDatabaseClusterInfo 实例。
        """
        self._ensure_connected()
        cache_key = f"db_cluster:{db_cluster_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            raw = dxpy.api.database_describe(db_cluster_id)  # type: ignore
            result = DXDatabaseClusterInfo.model_validate(raw)
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(
                e, f"Failed to describe database cluster '{db_cluster_id}'"
            )
            raise

    def get_database_schema(
        self,
        database_id: str,
        table_name: str | None = None,
        *,
        refresh: bool = False,
    ) -> list[DXDatabaseTable]:
        """查看数据库中可用的数据表。

        UKB-RAP 的 database 为 dnax 类型（Parquet 存储），无 SQL schema。
        本方法通过 ``database_list_folder`` 浏览顶层目录结构来列出数据表。
        结果按 database_id 缓存。
        """
        cache_key = f"db_schema:{database_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached_tables = self._cache.get(cache_key)
            if cached_tables is not None:
                if table_name:
                    return [t for t in cached_tables if t.name == table_name]
                return cached_tables

        self._ensure_connected()
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
            # 提取表名：取最后一层目录，去掉前缀和尾斜杠
            # 格式: "{hash}/database-{id}/{table_name}/"
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

        # 缓存全量表列表（不含 table_name 过滤）
        self._cache.set(cache_key, tables)
        return tables

    def query_database(
        self,
        database_id: str,
        entity_fields: list[str],
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """从数据库关联的数据集中提取指定字段并返回 DataFrame。

        UKB-RAP 的 database 为 dnax 类型，数据提取须通过关联的 Dataset record
        调用 ``dx extract_dataset``。若未提供 *dataset_ref*，自动查找。

        Args:
            database_id: DNAnexus database ID。
            entity_fields: ``"entity.field_name"`` 格式的字段列表。
            dataset_ref: 数据集引用。为 None 时自动查找。
            refresh: 为 True 时跳过缓存，强制从云端获取。
        """
        if not entity_fields:
            return pd.DataFrame()

        cache_key = f"db_query:{database_id}:{','.join(sorted(entity_fields))}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        if dataset_ref is None:
            _, dataset_ref = self.find_dataset()

        logger.info(
            "Extracting %d fields from database '%s' via dataset '%s'",
            len(entity_fields),
            database_id,
            dataset_ref,
        )
        result = self.extract_fields(
            entity_fields, dataset_ref=dataset_ref, refresh=refresh
        )
        self._cache.set(cache_key, result)
        return result

    def download_database_query(
        self,
        database_id: str,
        output_path: str,
        entity_fields: list[str],
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> Path:
        """从数据库关联的数据集中提取指定字段并下载为 CSV 文件。

        Args:
            database_id: DNAnexus database ID。
            output_path: 本地 CSV 文件保存路径。
            entity_fields: ``"entity.field_name"`` 格式的字段列表。
            dataset_ref: 数据集引用。为 None 时自动查找。
            refresh: 为 True 时跳过缓存，强制从云端获取。
        """
        df = self.query_database(
            database_id, entity_fields, dataset_ref, refresh=refresh
        )

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

        logger.info(
            "Downloaded %d rows (%d fields) from database '%s' to '%s'",
            len(df),
            len(entity_fields),
            database_id,
            path,
        )
        return path

    # ═══════════════════════════════════════════════════════════════════════
    #  数据集操作 (UKB-RAP)
    # ═══════════════════════════════════════════════════════════════════════

    def find_dataset(
        self,
        name_pattern: str = "app*.dataset",
        *,
        refresh: bool = False,
    ) -> tuple[str, str]:
        """在当前项目中查找 UKB Dataset record。

        结果会被缓存，后续调用直接返回缓存值。

        Args:
            name_pattern: 数据集名称匹配模式。
            refresh: 为 True 时跳过缓存，强制从云端获取。

        Returns:
            (dataset_id, dataset_ref) 元组。
        Raises:
            DXFileNotFoundError: 未找到匹配的 Dataset record。
        """
        if refresh and self._cached_dataset_ref:
            self._cache.last_status = CacheStatus.SKIP
        if not refresh and self._cached_dataset_ref:
            dataset_id = self._cached_dataset_ref.split(":")[-1]
            return dataset_id, self._cached_dataset_ref

        self._ensure_connected()
        project_id = self._require_project()
        datasets = self.find_data_objects(
            classname="record",
            name_pattern=name_pattern,
            limit=10,
        )
        for obj in datasets:
            rec = self.get_record(obj.id)
            types = rec.types or []
            if "Dataset" in types:
                self._cached_dataset_ref = f"{project_id}:{obj.id}"
                return obj.id, self._cached_dataset_ref

        raise DXFileNotFoundError(
            f"No Dataset record matching '{name_pattern}' found in project "
            f"'{project_id}'. Make sure the UK Biobank dataset has been "
            f"dispensed to this project."
        )

    def get_data_dictionary(
        self,
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """通过 ``dx extract_dataset -ddd`` 提取数据字典。

        结果按 dataset_ref 缓存，同一数据集重复调用直接返回缓存。
        """
        if dataset_ref is None:
            _, dataset_ref = self.find_dataset()

        cache_key = f"data_dictionary:{dataset_ref}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        env = self._make_subprocess_env()

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "dx",
                "extract_dataset",
                dataset_ref,
                "-ddd",
                "--delimiter",
                ",",
            ]
            logger.info("Running: %s", " ".join(cmd))
            try:
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    env=env,
                )
            except subprocess.CalledProcessError as e:
                raise DXAPIError(
                    f"dx extract_dataset -ddd failed: {e.stderr}",
                    status_code=e.returncode,
                    dx_error=e,
                ) from e

            pattern = str(Path(tmpdir) / "*.data_dictionary.csv")
            matches = glob.glob(pattern)
            if not matches:
                raise DXAPIError(
                    f"dx extract_dataset -ddd did not generate a data_dictionary CSV. "
                    f"stderr: {result.stderr}",
                )

            df = pd.read_csv(matches[0])
            logger.info("Loaded data dictionary: %d fields (from API)", len(df))
            self._cache.set(cache_key, df)
            return df

    def list_fields(
        self,
        entity: str | None = None,
        name_pattern: str | None = None,
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """列出数据集中的可用字段（精简视图）。

        底层调用 ``get_data_dictionary`` 获取全量数据字典，然后筛选并
        只保留 entity / name / type / title 四列。
        """
        df = self.get_data_dictionary(dataset_ref=dataset_ref, refresh=refresh)

        if entity:
            df = df[df["entity"] == entity]
        if name_pattern:
            df = df[df["name"].str.lower().str.contains(name_pattern.lower())]

        cols = ["entity", "name", "type", "title"]
        result = df[cols].reset_index(drop=True)
        logger.info("list_fields: %d fields matched", len(result))
        return result

    def extract_fields(
        self,
        entity_fields: list[str],
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """通过 ``dx extract_dataset`` 提取指定字段数据。"""
        if not entity_fields:
            return pd.DataFrame()

        cache_key = f"extract:{dataset_ref or '_'}:{','.join(sorted(entity_fields))}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        if dataset_ref is None:
            _, dataset_ref = self.find_dataset()

        env = self._make_subprocess_env()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "extract.csv"
            fields_arg = ",".join(entity_fields)
            cmd = [
                "dx",
                "extract_dataset",
                dataset_ref,
                "--fields",
                fields_arg,
                "--delimiter",
                ",",
                "--output",
                str(output_path),
            ]
            logger.info("Running: %s", " ".join(cmd))
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )
            except subprocess.CalledProcessError as e:
                raise DXAPIError(
                    f"dx extract_dataset failed: {e.stderr}",
                    status_code=e.returncode,
                    dx_error=e,
                ) from e

            if not output_path.exists():
                return pd.DataFrame()

            result = pd.read_csv(output_path)
            self._cache.set(cache_key, result)
            return result

    def generate_dataset_sql(
        self,
        entity_fields: list[str],
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> str:
        """生成数据集的 SQL 查询字符串。

        调用 vizserver /viz-query/3.0/{dataset}/raw-query 端点生成完整 SQL。
        不需要实际执行查询，直接获取生成的 SQL 字符串。
        """
        from . import cohort as cohort_mod

        self._ensure_connected()
        project_id = self._require_project()

        # 解析 dataset 引用
        if dataset_ref is None:
            _, dataset_ref = self.find_dataset()

        parts = dataset_ref.split(":")
        dataset_record_id = parts[-1]
        dataset_project = parts[0] if len(parts) > 1 else project_id

        # 获取 vizserver 信息
        try:
            viz_info = cohort_mod.get_visualize_info(dataset_record_id, dataset_project)
        except Exception as e:
            raise DXAPIError(
                f"Failed to get visualize info for dataset '{dataset_record_id}': {e}",
                dx_error=e,
            ) from e

        # 构建 payload
        # 字段格式：key 使用字段名（如 "p3_i0"），value 使用完整路径（如 "participant$p3_i0"）
        # 对于 "eid" 这类无 entity 前缀的字段，默认视为 participant 实体
        def _make_field_entry(f: str) -> dict[str, str]:
            parts = f.split(".")
            field_name = parts[-1]  # key: 字段名
            if len(parts) == 1:
                # 无 entity 前缀，默认 participant 实体
                entity_path = f"participant${field_name}"
            else:
                entity_path = "$".join(parts)
            return {field_name: entity_path}

        base_sql = viz_info.get("baseSql") or viz_info.get("base_sql")
        payload: dict[str, Any] = {
            "project_context": dataset_project,
            "fields": [_make_field_entry(f) for f in entity_fields],
        }
        if base_sql is not None:
            payload["base_sql"] = base_sql

        # 调用 vizserver 生成 SQL
        resource = (
            viz_info["url"]
            + "/viz-query/3.0/"
            + viz_info["dataset"]
            + "/raw-query"
        )
        try:
            resp = dxpy.DXHTTPRequest(
                resource=resource, data=payload, prepend_srv=False,
            )
        except Exception as e:
            raise DXAPIError(
                f"Failed to generate SQL for dataset '{viz_info['dataset']}': {e}",
                dx_error=e,
            ) from e

        if "error" in resp:
            raise DXAPIError(
                f"Vizserver error: {resp['error']}",
            )

        logger.info(
            "Generated SQL for %d fields from dataset '%s'",
            len(entity_fields),
            dataset_ref,
        )
        return resp["sql"]

    # ═══════════════════════════════════════════════════════════════════════
    #  Cohort 操作
    # ═══════════════════════════════════════════════════════════════════════

    def create_cohort(
        self,
        name: str,
        filters: dict[str, Any],
        *,
        dataset_ref: str | None = None,
        folder: str = "/",
        description: str = "",
        entity_fields: list[str] | None = None,
    ) -> DXCohortInfo:
        """基于筛选条件在当前项目中创建 cohort。"""
        from . import cohort as cohort_mod

        self._ensure_connected()
        project_id = self._require_project()

        # 1. 解析 dataset 引用
        if dataset_ref is None:
            _, dataset_ref = self.find_dataset()

        parts = dataset_ref.split(":")
        dataset_record_id = parts[-1]
        dataset_project = parts[0] if len(parts) > 1 else project_id

        # 2. 获取 vizserver 信息
        viz_info = cohort_mod.get_visualize_info(dataset_record_id, dataset_project)
        base_sql = viz_info.get("baseSql") or viz_info.get("base_sql")

        # 3. 构建 filter payload
        filter_payload: dict[str, Any] = {
            "filters": filters,
            "project_context": dataset_project,
        }
        if base_sql is not None:
            filter_payload["base_sql"] = base_sql

        # 4. 生成 SQL
        sql = cohort_mod.generate_cohort_sql(viz_info, filter_payload)

        # 5. 创建 cohort record
        record_payload = cohort_mod.build_cohort_record_payload(
            name=name,
            folder=folder,
            project=project_id,
            viz_info=viz_info,
            filters=filter_payload["filters"],
            sql=sql,
            description=description,
            entity_fields=entity_fields,
        )
        cohort_id = cohort_mod.create_cohort_record(record_payload)

        logger.info(
            "Created cohort '%s' (%s) in project '%s'",
            name,
            cohort_id,
            project_id,
        )

        return DXCohortInfo(
            id=cohort_id,
            name=name,
            project=project_id,
            folder=folder,
            description=description,
            entity_fields=entity_fields or [],
        )

    def list_cohorts(
        self,
        name_pattern: str | None = None,
        limit: int = 100,
        *,
        refresh: bool = True,
    ) -> list[DXRecordInfo]:
        """列出当前项目中的 cohort record。

        通过 ``dxpy.find_data_objects`` 的 ``type`` 参数在平台侧过滤
        ``CohortBrowser`` 类型，避免客户端二次过滤。

        结果按 project + name_pattern + limit 缓存。
        """
        self._ensure_connected()
        project = self._require_project()

        cache_key = f"cohorts:{project}:{name_pattern or ''}:{limit}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            kwargs: dict[str, Any] = {
                "classname": "record",
                "typename": "CohortBrowser",
                "project": project,
                "describe": True,
                "limit": limit,
            }
            if name_pattern:
                kwargs["name"] = name_pattern
                kwargs["name_mode"] = self._resolve_name_mode(name_pattern)
            result = [
                DXRecordInfo.model_validate(r["describe"])
                for r in dxpy.find_data_objects(**kwargs)
            ]
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(e, "Failed to list cohorts")
            raise

    def get_cohort(
        self,
        cohort_id: str,
        *,
        refresh: bool = False,
    ) -> DXRecordInfo:
        """获取 cohort record 详情。

        Args:
            cohort_id: Cohort record ID (record-xxxx)。
            refresh: 为 True 时跳过缓存。

        Returns:
            DXRecordInfo，details 中包含 filters、sql、dataset 等字段。
        """
        cache_key = f"cohort:{cohort_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            record = DXRecord(cohort_id, project=self._current_project_id or None)
            desc = record.describe()
            details = record.get_details()
            model = DXRecordInfo.model_validate(desc)
            model.details = details  # type: ignore[attr-defined]
            self._cache.set(cache_key, model)
            return model
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to get cohort '{cohort_id}'")
            raise

    def find_cohort(
        self,
        name_pattern: str | None = None,
        *,
        refresh: bool = False,
    ) -> DXRecordInfo:
        """在当前项目中查找 cohort。

        Args:
            name_pattern: 名称匹配模式。为 None 时返回第一个 cohort。
            refresh: 为 True 时跳过缓存。

        Returns:
            匹配的 DXRecordInfo。

        Raises:
            DXFileNotFoundError: 未找到 cohort。
        """
        cohorts = self.list_cohorts(
            name_pattern=name_pattern, limit=100, refresh=refresh
        )
        if not cohorts:
            pattern_desc = f"matching '{name_pattern}'" if name_pattern else ""
            raise DXFileNotFoundError(
                f"No cohort {pattern_desc} found in project '{self._current_project_id}'."
            )
        return cohorts[0]

    def delete_cohort(self, cohort_id: str) -> None:
        """删除当前项目中的 cohort record。

        Args:
            cohort_id: Cohort record ID (record-xxxx)。

        Raises:
            DXFileNotFoundError: record 不存在或无权限。
        """
        self._ensure_connected()
        project_id = self._require_project()
        try:
            dxpy.DXHTTPRequest(
                "/%s/remove" % cohort_id,
                {"project": project_id},
            )
            logger.info("Deleted cohort '%s' from project '%s'", cohort_id, project_id)
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to delete cohort '{cohort_id}'")
            raise

    def extract_cohort_fields(
        self,
        cohort_id: str,
        entity_fields: list[str],
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """提取 cohort 内参与者的指定字段数据。

        通过 ``dx extract_dataset <cohort_ref> --fields ...`` 实现。
        """
        self._ensure_connected()
        project_id = self._require_project()

        if not entity_fields:
            return pd.DataFrame()

        cache_key = f"cohort_data:{cohort_id}:{','.join(sorted(entity_fields))}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        cohort_ref = f"{project_id}:{cohort_id}"
        env = self._make_subprocess_env()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "cohort_extract.csv"
            fields_arg = ",".join(entity_fields)
            cmd = [
                "dx",
                "extract_dataset",
                cohort_ref,
                "--fields",
                fields_arg,
                "--delimiter",
                ",",
                "--output",
                str(output_path),
            ]
            logger.info("Running: %s", " ".join(cmd))
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )
            except subprocess.CalledProcessError as e:
                raise DXAPIError(
                    f"dx extract_dataset (cohort) failed: {e.stderr}",
                    status_code=e.returncode,
                    dx_error=e,
                ) from e

            if not output_path.exists():
                return pd.DataFrame()

            df = pd.read_csv(output_path)
            self._cache.set(cache_key, df)
            logger.info(
                "Extracted %d rows, %d fields from cohort '%s'",
                len(df),
                len(entity_fields),
                cohort_id,
            )
            return df

    def download_cohort(
        self,
        cohort_id: str,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """下载 cohort 的所有关联字段数据。

        从 cohort record 的 ``details.fields`` 中读取字段列表，通过 vizserver API 提取数据。
        不使用 CLI subprocess，避免大量字段时超过 OS 参数长度限制。
        """
        from . import cohort as cohort_mod

        self._ensure_connected()
        project_id = self._require_project()

        # 从 cohort record 读取 details.fields
        try:
            desc: dict[str, Any] = dxpy.describe(  # type: ignore[assignment]
                cohort_id,
                fields={"properties", "details"},
                default_fields=True,
            )
        except Exception as e:
            raise DXCohortError(
                f"Failed to describe cohort '{cohort_id}': {e}",
                dx_error=e,
            ) from e

        details: dict[str, Any] = desc.get("details") or {}
        entity_fields: list[str] = details.get("fields", [])
        entity_fields = convert_fields(entity_fields)

        if not entity_fields:
            raise DXCohortError(
                f"Cohort '{cohort_id}' has no associated fields in details.fields.",
            )

        cache_key = f"cohort_data:{cohort_id}:all"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            viz_info = cohort_mod.get_visualize_info(cohort_id, project_id)
        except Exception as e:
            raise DXCohortError(
                f"Failed to get visualize info for cohort '{cohort_id}': {e}",
                dx_error=e,
            ) from e

        payload: dict[str, Any] = {
            "project_context": project_id,
            "fields": [{f: f.replace(".", "$", 1)} for f in entity_fields],
        }
        if viz_info.get("baseSql"):
            payload["base_sql"] = viz_info["baseSql"]
        if viz_info.get("filters"):
            payload["filters"] = viz_info["filters"]

        resource = (
            viz_info["url"] + "/data/3.0/" + viz_info["dataset"] + "/raw"
        )
        try:
            resp = dxpy.DXHTTPRequest(
                resource=resource, data=payload, prepend_srv=False,
            )
        except Exception as e:
            raise DXCohortError(
                f"Failed to query cohort data: {e}",
                dx_error=e,
            ) from e

        results = resp.get("results", [])
        df = pd.DataFrame(results)
        self._cache.set(cache_key, df)
        logger.info(
            "Downloaded %d rows, %d fields from cohort '%s'",
            len(df),
            len(entity_fields),
            cohort_id,
        )
        return df

    def get_cohort_viz_info(
        self,
        cohort_id: str,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """获取 cohort 的 vizserver viz_info。

        包含 url、dataset、recordTypes、baseSql、filters 等字段，
        用于生成 SQL 或预览数据。

        Args:
            cohort_id: Cohort record ID (record-xxxx)。
            refresh: 为 True 时跳过缓存。

        Returns:
            viz_info dict，包含 url、dataset、filters、baseSql 等字段。
        """
        from . import cohort as cohort_mod

        self._ensure_connected()
        project = self._require_project()

        cache_key = f"cohort_viz_info:{cohort_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            viz_info = cohort_mod.get_visualize_info(
                cohort_id, project, cohort_browser=True,
            )
        except Exception as e:
            raise DXCohortError(
                f"Failed to get viz info for cohort '{cohort_id}': {e}",
                dx_error=e,
            ) from e

        self._cache.set(cache_key, viz_info)
        return viz_info

    def generate_cohort_sql(
        self,
        cohort_id: str,
        entity_fields: list[str] | None = None,
        *,
        refresh: bool = False,
    ) -> str:
        """生成 cohort 的 SQL 查询字符串。

        调用 vizserver /viz-query/3.0/{dataset}/raw-cohort-query 端点。

        Args:
            cohort_id: Cohort record ID。
            entity_fields: 要查询的字段列表（如 ["eid", "participant.sex"]）。
                为 None 时只返回基于 filters 的 participant ID 列表 SQL。
            refresh: 为 True 时跳过缓存。

        Returns:
            SQL 字符串（末尾带分号）。
        """
        self._ensure_connected()
        project = self._require_project()

        viz_info = self.get_cohort_viz_info(cohort_id, refresh=refresh)

        filter_payload: dict[str, Any] = {
            "project_context": project,
            "filters": viz_info.get("filters", {}),
        }
        if viz_info.get("baseSql"):
            filter_payload["base_sql"] = viz_info["baseSql"]

        if entity_fields:
            filter_payload["fields"] = [
                {f: "$".join(f.split("."))} for f in entity_fields
            ]

        resource = (
            viz_info["url"]
            + "/viz-query/3.0/"
            + viz_info["dataset"]
            + "/raw-cohort-query"
        )
        try:
            resp = dxpy.DXHTTPRequest(
                resource=resource, data=filter_payload, prepend_srv=False,
            )
        except Exception as e:
            raise DXCohortError(
                f"Failed to generate cohort SQL for '{cohort_id}': {e}",
                dx_error=e,
            ) from e

        if "error" in resp:
            raise DXCohortError(
                f"vizserver error: {resp['error']}",
            )
        return resp["sql"] + ";"

    def preview_cohort_data(
        self,
        cohort_id: str,
        entity_fields: list[str],
        *,
        limit: int = 100,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """预览 cohort 数据（不创建 cohort record）。

        通过 vizserver /data/3.0/raw 端点执行查询并返回结果。
        与 extract_cohort_fields 的区别是：本方法不需要 cohort.details.fields 非空。

        注意：字段格式为 ``entity$field``（如 ``participant$eid``），
        而非 dataset 的 ``entity.field`` 格式。

        Args:
            cohort_id: Cohort record ID。
            entity_fields: 要查询的字段列表（如 ``["participant$eid", "participant$sex"]``）。
            limit: 返回的最大行数（前端截取，不走 API limit）。
            refresh: 为 True 时跳过缓存。

        Returns:
            查询结果的 DataFrame。
        """
        self._ensure_connected()
        project = self._require_project()

        if not entity_fields:
            return pd.DataFrame()

        cache_key = f"cohort_preview:{cohort_id}:{','.join(sorted(entity_fields))}:{limit}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        viz_info = self.get_cohort_viz_info(cohort_id, refresh=refresh)

        # Cohort API requires entity$field format (not entity.field like datasets)
        payload: dict[str, Any] = {
            "project_context": project,
            "fields": [{f: f} for f in entity_fields],
        }
        if viz_info.get("baseSql"):
            payload["base_sql"] = viz_info["baseSql"]
        if viz_info.get("filters"):
            payload["filters"] = viz_info["filters"]

        resource = (
            viz_info["url"] + "/data/3.0/" + viz_info["dataset"] + "/raw"
        )
        try:
            resp = dxpy.DXHTTPRequest(
                resource=resource, data=payload, prepend_srv=False,
            )
        except Exception as e:
            raise DXCohortError(
                f"Failed to preview cohort data for '{cohort_id}': {e}",
                dx_error=e,
            ) from e

        if "error" in resp:
            raise DXCohortError(
                f"vizserver error: {resp.get('error')}",
            )

        results = resp.get("results", [])
        df = pd.DataFrame(results[:limit])
        self._cache.set(cache_key, df)
        logger.info(
            "Previewed %d rows from cohort '%s'",
            len(df),
            cohort_id,
        )
        return df

    # ═══════════════════════════════════════════════════════════════════════
    #  Job 操作
    # ═══════════════════════════════════════════════════════════════════════

    def list_jobs(
        self,
        state: str | None = None,
        name_pattern: str | None = None,
        *,
        created_after: int | None = None,
        created_before: int | None = None,
        include_subjobs: bool = False,
        limit: int = 100,
        refresh: bool = False,
    ) -> list[DXJobInfo]:
        """列出当前项目中的 job。"""
        self._ensure_connected()
        project = self._require_project()
        cache_key = (
            f"jobs:{project}:{state or ''}:{name_pattern or ''}"
            f":{created_after or ''}:{created_before or ''}"
            f":{include_subjobs}:{limit}"
        )
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            kwargs: dict[str, Any] = {
                "project": project,
                "describe": True,
                "limit": limit,
            }
            if state:
                kwargs["state"] = state
            if name_pattern:
                kwargs["name"] = name_pattern
                kwargs["name_mode"] = self._resolve_name_mode(name_pattern)
            if created_after is not None:
                kwargs["created_after"] = created_after
            if created_before is not None:
                kwargs["created_before"] = created_before
            if include_subjobs:
                kwargs["include_subjobs"] = True
            result = [
                DXJobInfo.model_validate(r["describe"])
                for r in dxpy.find_jobs(**kwargs)
            ]
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(e, "Failed to list jobs")
            raise

    def describe_job(
        self,
        job_id: str,
        *,
        refresh: bool = False,
    ) -> DXJobInfo:
        """获取 job 完整描述。"""
        self._ensure_connected()
        cache_key = f"job:{job_id}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            job = dxpy.DXJob(job_id)
            desc = job.describe()
            result = DXJobInfo.model_validate(desc)
            self._cache.set(cache_key, result)
            return result
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to describe job '{job_id}'")
            raise

    def terminate_job(self, job_id: str) -> str:
        """终止指定 job。"""
        self._ensure_connected()
        try:
            job = dxpy.DXJob(job_id)
            job.terminate()
            self._cache.delete(f"job:{job_id}")
            logger.info("Terminated job '%s'", job_id)
            return job_id
        except DxPyDXError as e:
            self._handle_dx_error(e, f"Failed to terminate job '{job_id}'")
            raise

    def wait_on_job(
        self,
        job_id: str,
        *,
        interval: float = 2.0,
        timeout: float | None = None,
    ) -> DXJobInfo:
        """等待 job 到达终态，返回最终描述。"""
        import time

        self._ensure_connected()
        start = time.monotonic()
        try:
            job = dxpy.DXJob(job_id)
            kwargs: dict[str, Any] = {"interval": interval}
            if timeout is not None:
                kwargs["timeout"] = timeout
            job.wait_on_done(**kwargs)
        except DxPyDXError as e:
            err_str = str(e).lower()
            if "timed out" in err_str or "timeout" in err_str:
                raise DXJobError(
                    f"Timed out waiting for job '{job_id}' (timeout={timeout}s)",
                    dx_error=e,
                ) from e
            logger.warning("wait_on_done raised for job '%s': %s", job_id, e)
        except Exception as e:
            raise DXJobError(
                f"Error waiting for job '{job_id}': {e}",
                dx_error=e,
            ) from e

        final = self.describe_job(job_id, refresh=True)
        elapsed = time.monotonic() - start
        logger.info(
            "Job '%s' reached terminal state '%s' in %.1fs",
            job_id,
            final.state,
            elapsed,
        )
        return final

    # ── 内部工具 ──────────────────────────────────────────────────────────

    def _make_subprocess_env(self) -> dict[str, str]:
        """构建子进程环境变量，确保 ``dx`` CLI 能继承 security context。"""
        env = os.environ.copy()
        env["DX_SECURITY_CONTEXT"] = json.dumps(
            {
                "auth_token_type": "Bearer",
                "auth_token": self._config.auth_token,
            }
        )
        if self._current_project_id:
            env["DX_PROJECT_CONTEXT_ID"] = self._current_project_id
        return env


def convert_fields(fields: List[str]) -> List[str]:
    # Convert "$" into "."
    r1 = [i.replace("$", ".", 1) for i in fields]

    # Remove content after ";"
    r2 = [i.split(";")[0] for i in r1]

    # Convert to lowercase
    r3 = [i.lower() for i in r2]
    return r3
