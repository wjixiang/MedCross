"""Cohort 操作服务。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Protocol

import dxpy
import pandas as pd
from dxpy import DXRecord
from dxpy.exceptions import DXAPIError as DxPyDXAPIError
from dxpy.exceptions import DXError as DxPyDXError

from .cache import CacheStatus, ICache
from .cohort import (
    build_cohort_record_payload,
    create_cohort_record,
    generate_cohort_sql,
)
from .dx_exceptions import (
    DXAPIError,
    DXFileNotFoundError,
    translate_dx_error,
)
from .dx_models import DXCohortInfo, DXRecordInfo
from .vizserver import IVizserverClient

logger = logging.getLogger(__name__)


class ICohortContext(Protocol):
    """CohortService 对客户端的窄依赖协议。

    仅声明 ``find_dataset`` 用于 ``create_cohort`` 的自动发现。
    """

    def find_dataset(
        self,
        name_pattern: str = "app*.dataset",
        *,
        refresh: bool = False,
    ) -> tuple[str, str]: ...


class ICohortService(ABC):
    """Cohort 操作抽象接口。"""

    @abstractmethod
    def list_cohorts(
        self,
        project_id: str,
        name_pattern: str | None = None,
        limit: int = 100,
        *,
        refresh: bool = False,
    ) -> list[DXRecordInfo]:
        """列出项目中的 cohort record。"""

    @abstractmethod
    def get_cohort(
        self,
        project_id: str,
        cohort_id: str,
        *,
        refresh: bool = False,
    ) -> DXRecordInfo:
        """获取 cohort record 详情。"""

    @abstractmethod
    def find_cohort(
        self,
        project_id: str,
        name_pattern: str | None = None,
        *,
        refresh: bool = False,
    ) -> DXRecordInfo:
        """在项目中查找 cohort。"""

    @abstractmethod
    def create_cohort(
        self,
        project_id: str,
        name: str,
        filters: dict[str, Any],
        *,
        dataset_ref: str | None = None,
        folder: str = "/",
        description: str = "",
        entity_fields: list[str] | None = None,
    ) -> DXCohortInfo:
        """基于筛选条件创建 cohort。"""

    @abstractmethod
    def delete_cohort(self, project_id: str, cohort_id: str) -> None:
        """删除 cohort record。"""

    @abstractmethod
    def extract_cohort_fields(
        self,
        project_id: str,
        cohort_id: str,
        entity_fields: list[str],
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """提取 cohort 内参与者的指定字段数据。"""

    @abstractmethod
    def download_cohort(
        self,
        project_id: str,
        cohort_id: str,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """下载 cohort 的所有关联字段数据。"""


class CohortService(ICohortService):
    """Cohort 操作默认实现。

    Args:
        cache: 共享缓存实例。
        context: 客户端上下文，用于 find_dataset 自动发现。
        vizserver: vizserver 客户端实例。
    """

    def __init__(
        self,
        cache: ICache,
        context: ICohortContext,
        vizserver: IVizserverClient,
    ) -> None:
        self._cache = cache
        self._context = context
        self._vizserver = vizserver

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

    # ── 实现 ──────────────────────────────────────────────────────────

    def list_cohorts(
        self,
        project_id: str,
        name_pattern: str | None = None,
        limit: int = 100,
        *,
        refresh: bool = False,
    ) -> list[DXRecordInfo]:
        """列出当前项目中的 cohort record。

        通过 ``dxpy.find_data_objects`` 的 ``type`` 参数在平台侧过滤
        ``CohortBrowser`` 类型，避免客户端二次过滤。

        结果按 project + name_pattern + limit 缓存。
        """
        cache_key = f"cohorts:{project_id}:{name_pattern or ''}:{limit}"
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
                "project": project_id,
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
        project_id: str,
        cohort_id: str,
        *,
        refresh: bool = False,
    ) -> DXRecordInfo:
        """获取 cohort record 详情。

        Args:
            project_id: 项目 ID。
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
            record = DXRecord(cohort_id, project=project_id or None)
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
        project_id: str,
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
            project_id, name_pattern=name_pattern, limit=100, refresh=refresh
        )
        if not cohorts:
            pattern_desc = f"matching '{name_pattern}'" if name_pattern else ""
            raise DXFileNotFoundError(
                f"No cohort {pattern_desc} found in project '{project_id}'."
            )
        return cohorts[0]

    def create_cohort(
        self,
        project_id: str,
        name: str,
        filters: dict[str, Any],
        *,
        dataset_ref: str | None = None,
        folder: str = "/",
        description: str = "",
        entity_fields: list[str] | None = None,
    ) -> DXCohortInfo:
        """基于筛选条件在当前项目中创建 cohort。"""
        # 1. 解析 dataset 引用
        if dataset_ref is None:
            _, dataset_ref = self._context.find_dataset()

        parts = dataset_ref.split(":")
        dataset_record_id = parts[-1]
        dataset_project = parts[0] if len(parts) > 1 else project_id

        # 2. 获取 vizserver 信息
        viz_info = self._vizserver.get_visualize_info(
            dataset_record_id, dataset_project,
        )
        base_sql = viz_info.get("baseSql") or viz_info.get("base_sql")

        # 3. 构建 filter payload
        filter_payload: dict[str, Any] = {
            "filters": filters,
            "project_context": dataset_project,
        }
        if base_sql is not None:
            filter_payload["base_sql"] = base_sql

        # 4. 生成 SQL
        sql = generate_cohort_sql(viz_info, filter_payload, self._vizserver)

        # 5. 创建 cohort record
        record_payload = build_cohort_record_payload(
            name=name,
            folder=folder,
            project=project_id,
            viz_info=viz_info,
            filters=filter_payload["filters"],
            sql=sql,
            description=description,
            entity_fields=entity_fields,
        )
        cohort_id = create_cohort_record(record_payload)

        logger.info(
            "Created cohort '%s' (%s) in project '%s'",
            name, cohort_id, project_id,
        )

        return DXCohortInfo(
            id=cohort_id,
            name=name,
            project=project_id,
            folder=folder,
            description=description,
            entity_fields=entity_fields or [],
        )

    def delete_cohort(self, project_id: str, cohort_id: str) -> None:
        """删除当前项目中的 cohort record。

        Args:
            project_id: 项目 ID。
            cohort_id: Cohort record ID (record-xxxx)。

        Raises:
            DXFileNotFoundError: record 不存在或无权限。
        """
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
        project_id: str,
        cohort_id: str,
        entity_fields: list[str],
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """提取 cohort 内参与者的指定字段数据（纯 SDK，无 CLI 依赖）。

        通过 vizserver /data/3.0/raw API 实现，附带 cohort 的 base_sql 和 filters。
        """
        if not entity_fields:
            return pd.DataFrame()

        cache_key = f"cohort_data:{cohort_id}:{','.join(sorted(entity_fields))}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            viz_info = self._vizserver.get_visualize_info(cohort_id, project_id)
        except Exception as e:
            raise DXAPIError(
                f"Failed to get visualize info for cohort '{cohort_id}': {e}",
                dx_error=e,
            ) from e

        payload: dict[str, Any] = {
            "project_context": project_id,
            "fields": [{f: "$".join(f.split("."))} for f in entity_fields],
        }
        # Cohort-specific: add subsetting SQL and phenotype filters
        if viz_info.get("baseSql"):
            payload["base_sql"] = viz_info["baseSql"]
        if viz_info.get("filters"):
            payload["filters"] = viz_info["filters"]

        results = self._vizserver.query_raw_data(viz_info, payload)
        df = pd.DataFrame(results)
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
        project_id: str,
        cohort_id: str,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """下载 cohort 的所有关联字段数据。

        从 cohort record 的 ``details.fields`` 中读取字段列表，然后提取对应数据。
        """
        try:
            desc = dxpy.describe(  # type: ignore[assignment]
                cohort_id,
                fields={"details"},
                default_fields=True,
            )
        except Exception as e:
            raise DXAPIError(
                f"Failed to describe cohort '{cohort_id}': {e}",
                dx_error=e,
            ) from e

        details = desc.get("details") or {}
        entity_fields = details.get("fields", [])
        if not entity_fields:
            raise DXAPIError(
                f"Cohort '{cohort_id}' has no associated fields in details.fields.",
            )

        return self.extract_cohort_fields(
            project_id, cohort_id, entity_fields, refresh=refresh,
        )
