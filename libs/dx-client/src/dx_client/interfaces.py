"""DNAnexus 平台数据访问抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from .cache.base import CacheStatus


if TYPE_CHECKING:
    from .dx_models import (
        DXCohortInfo,
        DXDataObject,
        DXDatabaseClusterInfo,
        DXDatabaseInfo,
        DXDatabaseTable,
        DXFileInfo,
        DXJobInfo,
        DXProject,
        DXRecordInfo,
    )


class IDXClient(ABC):
    """DNAnexus 平台数据访问抽象接口。

    子类需实现所有标注为 ``@abstractmethod`` 的方法。
    所有数据读取方法默认命中缓存，传入 ``refresh=True`` 可强制刷新。
    通过 ``close()`` 释放底层资源，建议配合上下文管理器使用。
    """

    @property
    @abstractmethod
    def current_project_id(self) -> str:
        """当前项目上下文 ID。"""

    @property
    @abstractmethod
    def cache_status(self) -> CacheStatus:
        """最近一次数据读取的缓存状态。"""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """是否已建立与平台的连接。"""

    # ── 项目操作 ──────────────────────────────────────────────────────────

    @abstractmethod
    def list_projects(
        self, name_pattern: str | None = None, *, refresh: bool = False,
    ) -> list[DXProject]:
        """列出有权限访问的项目。"""

    @abstractmethod
    def get_project(
        self, project_id: str, *, refresh: bool = False,
    ) -> DXProject:
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
        *,
        refresh: bool = False,
    ) -> list[DXFileInfo]:
        """列出当前项目中的文件。"""

    @abstractmethod
    def describe_file(
        self, file_id: str, *, refresh: bool = False,
    ) -> DXFileInfo:
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
        *,
        refresh: bool = False,
    ) -> list[DXRecordInfo]:
        """列出当前项目中的记录。"""

    @abstractmethod
    def get_record(
        self, record_id: str, *, refresh: bool = False,
    ) -> DXRecordInfo:
        """获取记录详情（含 details 内容）。"""

    # ── 通用搜索 ──────────────────────────────────────────────────────────

    @abstractmethod
    def find_data_objects(
        self,
        classname: str = "file",
        name_pattern: str | None = None,
        properties: dict[str, str] | None = None,
        limit: int = 100,
        *,
        refresh: bool = False,
    ) -> list[DXDataObject]:
        """在当前项目中搜索数据对象。"""

    # ── 数据库操作 ──────────────────────────────────────────────────────────

    @abstractmethod
    def list_databases(
        self,
        name_pattern: str | None = None,
        limit: int = 100,
        *,
        refresh: bool = False,
    ) -> list[DXDatabaseInfo]:
        """列出当前项目中的 database 数据对象。"""

    @abstractmethod
    def get_database(
        self, database_id: str, *, refresh: bool = False,
    ) -> DXDatabaseInfo:
        """获取 database 数据对象详情。"""

    @abstractmethod
    def find_database(
        self, name_pattern: str | None = None, *, refresh: bool = False,
    ) -> DXDatabaseInfo:
        """在当前项目中查找 database 数据对象。

        Args:
            name_pattern: 数据库名称匹配模式。为 None 时返回第一个 database。
            refresh: 为 True 时跳过缓存，强制从云端获取。

        Returns:
            匹配的 DXDatabaseInfo 实例。

        Raises:
            DXDatabaseNotFoundError: 未找到匹配的 database。
        """

    @abstractmethod
    def describe_database_cluster(
        self, db_cluster_id: str, *, refresh: bool = False,
    ) -> DXDatabaseClusterInfo:
        """获取数据库集群描述信息。

        Args:
            db_cluster_id: 数据库集群 ID (database-xxxx)。
            refresh: 为 True 时跳过缓存，强制从云端获取。

        Returns:
            DXDatabaseClusterInfo 实例。
        """

    @abstractmethod
    def get_database_schema(
        self,
        database_id: str,
        table_name: str | None = None,
        *,
        refresh: bool = False,
    ) -> list[DXDatabaseTable]:
        """查看数据库中可用的数据表。

        Args:
            database_id: DNAnexus database ID (database-xxxx)。
            table_name: 指定表名进行过滤。为 None 时返回所有表。
            refresh: 为 True 时跳过缓存，强制从云端获取。

        Returns:
            DXDatabaseTable 列表。
        """

    @abstractmethod
    def query_database(
        self,
        database_id: str,
        entity_fields: list[str],
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """从数据库关联的数据集中提取指定字段并返回 DataFrame。

        Args:
            database_id: DNAnexus database ID。
            entity_fields: ``"entity.field_name"`` 格式的字段列表。
            dataset_ref: 数据集引用。为 None 时自动查找。
            refresh: 为 True 时跳过缓存，强制从云端获取。

        Returns:
            包含查询结果的 pandas DataFrame。
        """

    @abstractmethod
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

        Returns:
            下载文件的 Path 对象。
        """

    # ── 数据集操作 (UKB-RAP) ──────────────────────────────────────────────

    @abstractmethod
    def find_dataset(
        self, name_pattern: str = "app*.dataset", *, refresh: bool = False,
    ) -> tuple[str, str]:
        """在当前项目中查找 UKB Dataset record.

        Args:
            name_pattern: 数据集名称匹配模式。
            refresh: 为 True 时跳过缓存，强制从云端获取。

        Returns:
            (dataset_id, dataset_ref) 元组，ref 格式为 ``"project-xxx:record-yyy"``。
        """

    @abstractmethod
    def get_data_dictionary(
        self, dataset_ref: str | None = None, *, refresh: bool = False,
    ) -> pd.DataFrame:
        """提取数据集的完整数据字典。

        Args:
            dataset_ref: 数据集引用。为 None 时自动查找项目中的 Dataset record。
            refresh: 为 True 时跳过缓存，强制从云端获取。

        Returns:
            DataFrame，包含 entity / name / type / title / description 等全部列。
        """

    @abstractmethod
    def list_fields(
        self,
        entity: str | None = None,
        name_pattern: str | None = None,
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """列出数据集中的可用字段（精简视图）。

        Args:
            entity: 按实体名过滤，如 ``"participant"``。为 None 时返回所有实体。
            name_pattern: 按字段名模糊匹配（大小写不敏感）。
            dataset_ref: 数据集引用。为 None 时自动查找。
            refresh: 为 True 时跳过缓存，强制从云端获取。

        Returns:
            DataFrame，包含 entity / name / type / title 四列。
        """

    @abstractmethod
    def extract_fields(
        self,
        entity_fields: list[str],
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """从数据集中提取指定字段。

        Args:
            entity_fields: ``"entity.field_name"`` 格式的字段列表。
            dataset_ref: 数据集引用。为 None 时自动查找。
            refresh: 为 True 时跳过缓存，强制从云端获取。

        Returns:
            DataFrame，包含 eid 列和请求的字段列。
        """

    @abstractmethod
    def generate_dataset_sql(
        self,
        entity_fields: list[str],
        dataset_ref: str | None = None,
        *,
        refresh: bool = False,
    ) -> str:
        """生成数据集的 SQL 查询字符串。

        调用 vizserver /viz-query/3.0/{dataset}/raw-query 端点生成完整 SQL。

        Args:
            entity_fields: 要查询的字段列表（如 ["eid", "participant.sex"]）。
            dataset_ref: 数据集引用。为 None 时自动查找。
            refresh: 为 True 时跳过缓存。

        Returns:
            生成的 SQL 字符串。
        """

    # ── Cohort 操作 ──────────────────────────────────────────────────────

    @abstractmethod
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
        """基于筛选条件在当前项目中创建 cohort。

        Args:
            name: Cohort 名称。
            filters: 原始 vizserver pheno_filters 结构，支持全部 26 种条件。
            dataset_ref: 源数据集引用 (``"project-xxx:record-yyy"``)。
                为 None 时自动调用 ``find_dataset()`` 查找。
            folder: 目标文件夹路径。
            description: Cohort 描述。
            entity_fields: 关联的字段列表（``"entity.field_name"`` 格式）。

        Returns:
            DXCohortInfo，包含新创建的 cohort 信息。

        Raises:
            DXCohortError: 创建失败等。
        """

    @abstractmethod
    def list_cohorts(
        self,
        name_pattern: str | None = None,
        limit: int = 100,
        *,
        refresh: bool = False,
    ) -> list[DXRecordInfo]:
        """列出当前项目中的 cohort record。

        通过平台侧 ``type=CohortBrowser`` 过滤，结果支持缓存。

        Args:
            name_pattern: 名称匹配模式。
            limit: 返回数量上限。
            refresh: 为 True 时跳过缓存。

        Returns:
            DXRecordInfo 列表。
        """

    @abstractmethod
    def get_cohort(
        self, cohort_id: str, *, refresh: bool = False,
    ) -> DXRecordInfo:
        """获取 cohort record 详情。

        Args:
            cohort_id: Cohort record ID。
            refresh: 为 True 时跳过缓存。

        Returns:
            DXRecordInfo，details 包含 filters、sql、dataset 等。
        """

    @abstractmethod
    def find_cohort(
        self, name_pattern: str | None = None, *, refresh: bool = False,
    ) -> DXRecordInfo:
        """在当前项目中查找 cohort。

        Args:
            name_pattern: 名称匹配模式。为 None 时返回第一个。
            refresh: 为 True 时跳过缓存。

        Returns:
            匹配的 DXRecordInfo。

        Raises:
            DXFileNotFoundError: 未找到 cohort。
        """

    @abstractmethod
    def delete_cohort(self, cohort_id: str) -> None:
        """删除当前项目中的 cohort record。

        Args:
            cohort_id: Cohort record ID (record-xxxx)。

        Raises:
            DXFileNotFoundError: record 不存在或无权限。
        """

    @abstractmethod
    def extract_cohort_fields(
        self,
        cohort_id: str,
        entity_fields: list[str],
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """提取 cohort 内参与者的指定字段数据。

        Args:
            cohort_id: Cohort record ID。
            entity_fields: ``"entity.field_name"`` 格式的字段列表。
            refresh: 为 True 时跳过缓存。

        Returns:
            包含 cohort 参与者数据的 DataFrame。

        Raises:
            DXCohortError: vizserver 请求失败。
        """

    @abstractmethod
    def download_cohort(
        self,
        cohort_id: str,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """下载 cohort 的所有关联字段数据。

        从 cohort record 的 ``details.fields`` 中读取字段列表，
        然后提取对应数据。

        Args:
            cohort_id: Cohort record ID。
            refresh: 为 True 时跳过缓存。

        Returns:
            包含 cohort 参与者数据的 DataFrame。

        Raises:
            DXCohortError: cohort 无关联字段或提取失败。
        """

    @abstractmethod
    def get_cohort_viz_info(
        self, cohort_id: str, *, refresh: bool = False,
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

    @abstractmethod
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

    @abstractmethod
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

        Args:
            cohort_id: Cohort record ID。
            entity_fields: 要查询的字段列表（如 ["eid", "participant.sex"]）。
            limit: 返回的最大行数（前端截取，不走 API limit）。
            refresh: 为 True 时跳过缓存。

        Returns:
            查询结果的 DataFrame。
        """

    # ── Job 操作 ──────────────────────────────────────────────────────

    @abstractmethod
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
        """列出当前项目中的 job。

        Args:
            state: 过滤 job 状态 (e.g. "running", "done", "failed", "terminated")。
            name_pattern: 名称匹配模式 (glob 或 regexp)。
            created_after: 创建时间下界 (Unix 毫秒时间戳)。
            created_before: 创建时间上界 (Unix 毫秒时间戳)。
            include_subjobs: 是否包含子 job。
            limit: 返回数量上限。
            refresh: 为 True 时跳过缓存。

        Returns:
            DXJobInfo 列表。
        """

    @abstractmethod
    def describe_job(
        self, job_id: str, *, refresh: bool = False,
    ) -> DXJobInfo:
        """获取 job 完整描述。

        Args:
            job_id: Job ID (job-xxxx)。
            refresh: 为 True 时跳过缓存。

        Returns:
            DXJobInfo 实例。

        Raises:
            DXFileNotFoundError: job 不存在或无权限。
        """

    @abstractmethod
    def terminate_job(self, job_id: str) -> str:
        """终止指定 job。

        Args:
            job_id: Job ID (job-xxxx)。

        Returns:
            终止的 job ID。

        Raises:
            DXJobError: 终止失败。
        """

    @abstractmethod
    def wait_on_job(
        self,
        job_id: str,
        *,
        interval: float = 2.0,
        timeout: float | None = None,
    ) -> DXJobInfo:
        """等待 job 到达终态，返回最终描述。

        阻塞当前线程轮询直到 job 进入 done/failed/terminated 状态。

        Args:
            job_id: Job ID (job-xxxx)。
            interval: 轮询间隔（秒）。
            timeout: 最大等待时间（秒）。为 None 时无限等待。

        Returns:
            终态 DXJobInfo 实例。

        Raises:
            DXJobError: 等待超时。
        """

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def close(self) -> None:
        """释放资源（子类可覆盖）。"""

    def __enter__(self) -> "IDXClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
