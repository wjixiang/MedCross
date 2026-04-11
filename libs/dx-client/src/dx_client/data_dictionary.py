"""数据字典查询服务。

从 DXClient 中提取的数据集发现、数据字典解析、字段列表和字段提取操作。
通过依赖注入接入 DXClient。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

import pandas as pd

from .cache import CacheStatus, ICache
from .cohort import get_dataset_descriptor
from .dx_exceptions import DXAPIError, DXFileNotFoundError
from .vizserver import IVizserverClient

if TYPE_CHECKING:
    from .dx_models import DXDataObject, DXRecordInfo

logger = logging.getLogger(__name__)


class IRecordFinder(Protocol):
    """DXClient 中被 DataDictionaryService 使用的子集协议。"""

    def find_data_objects(
        self,
        classname: str = "file",
        name_pattern: str | None = None,
        properties: dict[str, str] | None = None,
        limit: int = 100,
        *,
        refresh: bool = False,
    ) -> list[DXDataObject]: ...

    def get_record(
        self, record_id: str, *, refresh: bool = False,
    ) -> DXRecordInfo: ...


class IDataDictionaryService(ABC):
    """数据字典查询操作抽象接口。"""

    @abstractmethod
    def invalidate_dataset_cache(self) -> None:
        """清除缓存的 dataset 引用。在项目切换时调用。"""

    @abstractmethod
    def find_dataset(
        self,
        project_id: str,
        name_pattern: str = "app*.dataset",
        *,
        refresh: bool = False,
    ) -> tuple[str, str]:
        """在指定项目中查找 UKB Dataset record。

        Args:
            project_id: 项目上下文 ID。
            name_pattern: 数据集名称匹配模式。
            refresh: 为 True 时跳过缓存。

        Returns:
            (dataset_id, dataset_ref) 元组。
        """

    @abstractmethod
    def get_data_dictionary(
        self,
        project_id: str,
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """通过解析 dataset descriptor 获取数据字典。

        Args:
            project_id: 项目上下文 ID。
            dataset_ref: 数据集引用。为 None 时自动查找。
            refresh: 为 True 时跳过缓存。

        Returns:
            包含全部字段的 DataFrame。
        """

    @abstractmethod
    def list_fields(
        self,
        project_id: str,
        entity: str | None = None,
        name_pattern: str | None = None,
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """列出数据集中的可用字段。

        Args:
            project_id: 项目上下文 ID。
            entity: 按实体名过滤。
            name_pattern: 按字段名模糊匹配。
            dataset_ref: 数据集引用。为 None 时自动查找。
            refresh: 为 True 时跳过缓存。

        Returns:
            按条件筛选后的 DataFrame。
        """


class DataDictionaryService(IDataDictionaryService):
    """数据字典查询操作的默认实现。

    Args:
        cache: 可插拔的缓存实例。
        record_finder: 提供 find_data_objects / get_record 的对象。
        vizserver: vizserver 客户端实例。
    """

    def __init__(
        self,
        cache: ICache,
        record_finder: IRecordFinder,
        vizserver: IVizserverClient,
    ) -> None:
        self._cache = cache
        self._record_finder = record_finder
        self._vizserver = vizserver
        self._cached_dataset_ref: str | None = None

    def invalidate_dataset_cache(self) -> None:
        """清除缓存的 dataset 引用。"""
        self._cached_dataset_ref = None

    def find_dataset(
        self,
        project_id: str,
        name_pattern: str = "app*.dataset",
        *,
        refresh: bool = False,
    ) -> tuple[str, str]:
        """在当前项目中查找 UKB Dataset record。

        结果会被缓存，后续调用直接返回缓存值。
        """
        if refresh and self._cached_dataset_ref:
            self._cache.last_status = CacheStatus.SKIP
        if not refresh and self._cached_dataset_ref:
            dataset_id = self._cached_dataset_ref.split(":")[-1]
            return dataset_id, self._cached_dataset_ref

        datasets = self._record_finder.find_data_objects(
            classname="record",
            name_pattern=name_pattern,
            limit=10,
        )
        for obj in datasets:
            rec = self._record_finder.get_record(obj.id)
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
        project_id: str,
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """通过解析 dataset descriptor 获取数据字典（纯 SDK，无 CLI 依赖）。

        结果按 dataset_ref 缓存，同一数据集重复调用直接返回缓存。
        """
        if dataset_ref is None:
            dataset_id, dataset_ref = self.find_dataset(
                project_id, refresh=refresh,
            )
        else:
            dataset_id = dataset_ref.split(":")[-1]

        cache_key = f"data_dictionary:{dataset_ref}"
        if refresh:
            self._cache.last_status = CacheStatus.SKIP
        else:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            descriptor = get_dataset_descriptor(dataset_id, project_id)
        except Exception as e:
            raise DXAPIError(
                f"Failed to fetch dataset descriptor for '{dataset_id}': {e}",
                dx_error=e,
            ) from e

        model = descriptor.get("model", {})
        entities = model.get("entities", {})
        codings = model.get("codings", {})
        join_info = model.get("join_info", {})

        # Build join lookup: (from_entity, from_field) -> (to_entity, to_field, relationship)
        join_lookup: dict[tuple[str, str], tuple[str, str, str]] = {}
        for join_group in join_info:
            relationship = join_group.get("relationship", "")
            for edge in join_group.get("joins", []):
                from_parts = edge.get("from", "").split("$")
                to_parts = edge.get("to", "").split("$")
                if len(from_parts) == 2 and len(to_parts) == 2:
                    from_entity, from_field = from_parts[0], from_parts[1]
                    to_entity, to_field = to_parts[0], to_parts[1]
                    join_lookup[(from_entity, from_field)] = (
                        to_entity,
                        to_field,
                        relationship,
                    )

        rows: list[dict[str, Any]] = []
        for entity_name, entity_def in entities.items():
            is_main = entity_def.get("is_main_entity", False)
            pk_field = entity_def.get("primary_key", "")
            for field_name, field_def in entity_def.get("fields", {}).items():
                coding = field_def.get("coding_name")

                pk_type = ""
                if is_main and field_name == pk_field:
                    pk_type = "global_primary_key"
                elif field_name == pk_field:
                    pk_type = "primary_key"

                # Folder path → string
                folder_path = field_def.get("folder_path")
                if isinstance(folder_path, list):
                    folder_path = "/".join(folder_path)
                elif not folder_path:
                    folder_path = ""

                # Join relationship
                ref_entity_field = ""
                relationship = ""
                join_key = (entity_name, field_name)
                if join_key in join_lookup:
                    to_entity, to_field, rel = join_lookup[join_key]
                    ref_entity_field = f"{to_entity}.{to_field}"
                    relationship = rel

                rows.append({
                    "entity": entity_name,
                    "name": field_name,
                    "type": field_def.get("type", ""),
                    "primary_key_type": pk_type,
                    "title": field_def.get("title", ""),
                    "description": field_def.get("description", ""),
                    "coding_name": coding or "",
                    "concept": field_def.get("concept", ""),
                    "folder_path": folder_path,
                    "is_multi_select": field_def.get("is_multi_select", False),
                    "is_sparse_coding": field_def.get("is_sparse_coding", False),
                    "linkout": field_def.get("linkout", ""),
                    "longitudinal_axis_type": field_def.get(
                        "longitudinal_axis_type", ""
                    ),
                    "referenced_entity_field": ref_entity_field,
                    "relationship": relationship,
                    "units": field_def.get("units", ""),
                })

        df = pd.DataFrame(rows)
        logger.info("Loaded data dictionary: %d fields (from SDK)", len(df))
        self._cache.set(cache_key, df)
        return df

    def list_fields(
        self,
        project_id: str,
        entity: str | None = None,
        name_pattern: str | None = None,
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """列出数据集中的可用字段。

        底层调用 ``get_data_dictionary`` 获取全量数据字典，然后按条件筛选。
        """
        df = self.get_data_dictionary(
            project_id, dataset_ref=dataset_ref, refresh=refresh,
        )

        if entity:
            df = df[df["entity"] == entity]
        if name_pattern:
            df = df[df["name"].str.lower().str.contains(name_pattern.lower())]

        result = df.reset_index(drop=True)
        logger.info("list_fields: %d fields matched", len(result))
        return result
