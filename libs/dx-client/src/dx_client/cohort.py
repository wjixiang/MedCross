"""Cohort 创建纯 Python 实现。

从 dxpy CLI (dataset_utilities.py / cohort_filter_payload.py) 中提取的核心逻辑，
去掉 CLI 依赖，改为纯函数 + 异常抛出。
"""

from __future__ import annotations

import gzip
import io
import json
import logging
from collections import OrderedDict
from typing import Any

import dxpy
from .dx_exceptions import DXCohortError

logger = logging.getLogger(__name__)


# ── Vizserver 交互 ──────────────────────────────────────────────────────


def get_visualize_info(
    record_id: str,
    project: str,
    *,
    cohort_browser: bool = False,
) -> dict[str, Any]:
    """调用 ``/record-xxx/visualize`` 获取 vizserver 连接信息。

    Args:
        record_id: Dataset 或 CohortBrowser 的 record ID。
        project: 所属项目 ID。
        cohort_browser: 为 True 时返回 Cohort 特有的 filters 和 baseSql。
                      Dataset 应传 False，CohortBrowser 应传 True。

    Returns:
        vizserver 响应 dict，包含 url、dataset、databases、schema 等字段。
        当 cohort_browser=True 时额外包含 baseSql 和 filters 字段。

    Raises:
        DXCohortError: record 无效、版本不支持或权限不足。
    """
    try:
        resp = dxpy.DXHTTPRequest(
            "/%s/visualize" % record_id,
            {"project": project, "cohortBrowser": cohort_browser},
        )
    except Exception as e:
        raise DXCohortError(
            f"Failed to get visualize info for '{record_id}': {e}",
            dx_error=e,
        ) from e

    if resp.get("datasetVersion") != "3.0":
        raise DXCohortError(
            f"Unsupported dataset version '{resp.get('datasetVersion')}'. "
            "Only version 3.0 is supported."
        )

    record_types = resp.get("recordTypes", [])
    if "Dataset" not in record_types and "CohortBrowser" not in record_types:
        raise DXCohortError(
            f"Record '{record_id}' is not a Dataset or CohortBrowser. "
            f"Types: {record_types}"
        )

    return resp


def get_dataset_descriptor(record_id: str, project: str) -> dict[str, Any]:
    """下载并解析 dataset 的 gzipped JSON descriptor。

    Args:
        record_id: Dataset record ID。
        project: 所属项目 ID。

    Returns:
        解析后的 descriptor dict，包含 model、join_info 等字段。
    """
    try:
        desc = dxpy.describe(
            record_id,
            fields={"properties", "details"},
            default_fields=True,
        )
    except Exception as e:
        raise DXCohortError(
            f"Failed to describe dataset '{record_id}': {e}",
            dx_error=e,
        ) from e

    details: dict[str, Any] = desc.get("details", {})  # type: ignore[assignment]
    descriptor_link = details.get("descriptor")
    if not descriptor_link:
        raise DXCohortError(f"No descriptor found in dataset '{record_id}' details.")

    # 解析 $dnanexus_link
    if isinstance(descriptor_link, dict) and "$dnanexus_link" in descriptor_link:
        file_id = descriptor_link["$dnanexus_link"]
        if isinstance(file_id, dict):
            file_id = file_id.get("id", "")
    else:
        file_id = str(descriptor_link)

    try:
        file_obj = dxpy.DXFile(file_id, project=project, mode="rb")
        raw: bytes = file_obj.read()  # type: ignore[assignment]
        buf = io.BytesIO(raw)
        with gzip.open(buf, "rt", encoding="utf-8") as f:
            return json.load(f, object_pairs_hook=OrderedDict)
    except Exception as e:
        raise DXCohortError(
            f"Failed to read descriptor file '{file_id}': {e}",
            dx_error=e,
        ) from e


# ── SQL 生成 ────────────────────────────────────────────────────────────


def generate_cohort_sql(
    viz_info: dict[str, Any],
    filter_payload: dict[str, Any],
) -> str:
    """调用 vizserver 生成 cohort SQL。

    Args:
        viz_info: ``get_visualize_info()`` 的返回值。
        filter_payload: ``build_cohort_filter_payload()`` 的返回值。

    Returns:
        生成的 SQL 字符串（末尾带分号）。

    Raises:
        DXCohortError: vizserver 请求失败。
    """
    resource = (
        viz_info["url"] + "/viz-query/3.0/" + viz_info["dataset"] + "/raw-cohort-query"
    )
    try:
        resp = dxpy.DXHTTPRequest(
            resource=resource,
            data=filter_payload,
            prepend_srv=False,
        )
    except Exception as e:
        raise DXCohortError(
            f"Failed to generate cohort SQL: {e}",
            dx_error=e,
        ) from e

    return resp["sql"] + ";"


# ── Record 创建 ─────────────────────────────────────────────────────────


def build_cohort_record_payload(
    name: str,
    folder: str,
    project: str,
    viz_info: dict[str, Any],
    filters: dict[str, Any],
    sql: str,
    description: str = "",
    entity_fields: list[str] | None = None,
) -> dict[str, Any]:
    """组装 DXRecord 创建 payload。

    Args:
        name: Cohort 名称。
        folder: 目标文件夹路径。
        project: 目标项目 ID。
        viz_info: ``get_visualize_info()`` 的返回值。
        filters: pheno_filters dict。
        sql: 生成的 SQL。
        description: 可选描述。
        entity_fields: 关联的字段列表（``"entity.field_name"`` 格式）。

    Returns:
        传给 ``create_cohort_record()`` 的完整 payload。
    """
    base_sql = viz_info.get("baseSql") or viz_info.get("base_sql")
    combined = viz_info.get("combined")

    details: dict[str, Any] = {
        "databases": viz_info["databases"],
        "dataset": {"$dnanexus_link": viz_info["dataset"]},
        "description": description,
        "filters": filters,
        "schema": viz_info["schema"],
        "sql": sql,
        "version": "3.0",
    }
    if entity_fields:
        details["fields"] = entity_fields
    if base_sql:
        details["baseSql"] = base_sql
    if combined:
        details["combined"] = _cohort_combined_payload(combined)

    types = ["DatabaseQuery", "CohortBrowser"]
    if combined:
        types.append("CombinedDatabaseQuery")

    # links: dataset + all referenced databases
    links = [viz_info["dataset"]]
    for db in viz_info.get("databases", []):
        if isinstance(db, dict):
            # {"app_version": {"$dnanexus_link": "database-xxx"}} format
            for v in db.values():
                if isinstance(v, dict) and "$dnanexus_link" in v:
                    links.append(v["$dnanexus_link"])
        elif isinstance(db, str):
            links.append(db)

    return {
        "name": name,
        "folder": folder,
        "project": project,
        "types": types,
        "details": details,
        "links": links,
        "close": True,
    }


def _cohort_combined_payload(combined: dict[str, Any]) -> dict[str, Any]:
    """转换 combined source 为 $dnanexus_link 格式。"""
    result = dict(combined)
    result["source"] = [
        {"$dnanexus_link": {"id": s["id"], "project": s["project"]}}
        for s in combined["source"]
    ]
    return result


def create_cohort_record(payload: dict[str, Any]) -> str:
    """在 DNAnexus 平台上创建 cohort record。

    Args:
        payload: ``build_cohort_record_payload()`` 的返回值。

    Returns:
        新创建的 cohort record ID。

    Raises:
        DXCohortError: 创建失败。
    """
    try:
        links = payload.pop("links", None)
        input_params: dict[str, Any] = {
            "project": payload["project"],
            "name": payload["name"],
            "types": payload["types"],
            "details": payload["details"],
            "hidden": payload.get("hidden", False),
        }
        if payload.get("folder"):
            input_params["folder"] = payload["folder"]
        if payload.get("properties"):
            input_params["properties"] = payload["properties"]
        if payload.get("tags"):
            input_params["tags"] = payload["tags"]
        if payload.get("parents"):
            input_params["parents"] = payload["parents"]
        if links:
            input_params["links"] = links

        resp = dxpy.api.record_new(input_params)  # type: ignore
        return resp["id"]
    except Exception as e:
        raise DXCohortError(
            f"Failed to create cohort record: {e}",
            dx_error=e,
        ) from e
