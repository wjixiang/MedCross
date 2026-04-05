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
from functools import reduce
from typing import Any, Callable

import dxpy
from dxpy.bindings.dxrecord import new_dxrecord

from .dx_exceptions import DXAPIError, DXCohortError

logger = logging.getLogger(__name__)


# ── Vizserver 交互 ──────────────────────────────────────────────────────


def get_visualize_info(record_id: str, project: str) -> dict[str, Any]:
    """调用 ``/record-xxx/visualize`` 获取 vizserver 连接信息。

    Args:
        record_id: Dataset 或 CohortBrowser 的 record ID。
        project: 所属项目 ID。

    Returns:
        vizserver 响应 dict，包含 url、dataset、databases、schema 等字段。

    Raises:
        DXCohortError: record 无效、版本不支持或权限不足。
    """
    try:
        resp = dxpy.DXHTTPRequest(
            "/%s/visualize" % record_id,
            {"project": project, "cohortBrowser": False},
        )
    except Exception as e:
        raise DXCohortError(
            f"Failed to get visualize info for '{record_id}': {e}", dx_error=e,
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
            f"Failed to describe dataset '{record_id}': {e}", dx_error=e,
        ) from e

    descriptor_link = desc.get("details", {}).get("descriptor")
    if not descriptor_link:
        raise DXCohortError(
            f"No descriptor found in dataset '{record_id}' details."
        )

    # 解析 $dnanexus_link
    if isinstance(descriptor_link, dict) and "$dnanexus_link" in descriptor_link:
        file_id = descriptor_link["$dnanexus_link"]
        if isinstance(file_id, dict):
            file_id = file_id.get("id", "")
    else:
        file_id = str(descriptor_link)

    try:
        file_obj = dxpy.DXFile(file_id, project=project, mode="rb")
        raw = file_obj.read()
        buf = io.BytesIO(raw)
        with gzip.open(buf, "rt", encoding="utf-8") as f:
            return json.load(f, object_pairs_hook=OrderedDict)
    except Exception as e:
        raise DXCohortError(
            f"Failed to read descriptor file '{file_id}': {e}", dx_error=e,
        ) from e


# ── ID 校验 ─────────────────────────────────────────────────────────────


def validate_participant_ids(
    descriptor: dict[str, Any],
    project: str,
    viz_info: dict[str, Any],
    ids: list[str],
) -> tuple[list[Any], Callable]:
    """校验 participant ID 是否存在于 dataset 中。

    Args:
        descriptor: dataset descriptor dict。
        project: 数据集所属项目 ID。
        viz_info: ``get_visualize_info()`` 的返回值。
        ids: 待校验的 participant ID 列表。

    Returns:
        (类型转换后的 ID 列表, 转换函数)。

    Raises:
        DXCohortError: 不支持的 ID 类型或 ID 不存在于 dataset。
    """
    gpk = descriptor["model"]["global_primary_key"]
    entity_name = gpk["entity"]
    field_name = gpk["field"]

    field_mapping = (
        descriptor["model"]["entities"][entity_name]["fields"][field_name]["mapping"]
    )
    gpk_type = field_mapping["column_sql_type"]

    if gpk_type in ("integer", "bigint"):
        lambda_conv: Callable = lambda a, b: a + [int(b)]
    elif gpk_type in ("float", "double"):
        lambda_conv = lambda a, b: a + [float(b)]
    elif gpk_type == "string":
        lambda_conv = lambda a, b: a + [str(b)]
    else:
        raise DXCohortError(
            f"Unsupported primary key type '{gpk_type}'. "
            "Only string, integer, and float are supported."
        )

    id_list = reduce(lambda_conv, ids, [])
    entity_field = f"{entity_name}${field_name}"

    payload = {
        "project_context": project,
        "fields": [{field_name: entity_field}],
        "filters": {
            "pheno_filters": {
                "filters": {
                    entity_field: [{"condition": "in", "values": id_list}],
                },
            },
        },
    }

    try:
        resource = viz_info["url"] + "/data/3.0/" + viz_info["dataset"] + "/raw"
        resp_raw = dxpy.DXHTTPRequest(
            resource=resource, data=payload, prepend_srv=False,
        )
    except Exception as e:
        raise DXCohortError(
            f"Vizserver query failed during ID validation: {e}", dx_error=e,
        ) from e

    discovered = {result[field_name] for result in resp_raw.get("results", [])}

    if discovered != set(id_list):
        missing = set(id_list) - discovered
        raise DXCohortError(
            f"The following IDs not found in dataset '{viz_info['dataset']}': "
            f"{missing}"
        )

    return id_list, lambda_conv


# ── Filter payload 构建 ─────────────────────────────────────────────────


def _generate_pheno_filter(
    values: list[Any],
    entity: str,
    field: str,
    filters: dict[str, Any],
    lambda_conv: Callable,
) -> dict[str, Any]:
    """构建或修改 pheno_filters，添加 participant ID 的 ``in`` 条件。"""
    entity_field = f"{entity}${field}"
    entity_field_filter = {"condition": "in", "values": values}

    if "pheno_filters" not in filters:
        filters["pheno_filters"] = {"compound": [], "logic": "and"}

    pheno = filters["pheno_filters"]

    if "compound" not in pheno:
        filters["pheno_filters"] = {"compound": [pheno], "logic": "and"}
        pheno = filters["pheno_filters"]

    # 尝试合并到已有的 entity$field 过滤器
    for compound in pheno["compound"]:
        if "filters" not in compound or entity_field not in compound["filters"]:
            continue
        if "logic" in compound and compound["logic"] != "and":
            raise DXCohortError(
                "Cannot create cohort: existing filter logic is not 'and'."
            )
        primary_filters = []
        for pf in compound["filters"][entity_field]:
            if pf["condition"] == "exists":
                pass
            elif pf["condition"] == "in":
                values = sorted(
                    set(values) & set(reduce(lambda_conv, pf["values"], []))
                )
            elif pf["condition"] == "not-in":
                values = sorted(
                    set(values) - set(reduce(lambda_conv, pf["values"], []))
                )
            else:
                raise DXCohortError(
                    f"Cannot create cohort: unsupported filter condition "
                    f"'{pf['condition']}'."
                )
        primary_filters.append(entity_field_filter)
        compound["filters"][entity_field] = primary_filters
        return filters

    # 尝试添加到已有的 entity 过滤器（不同字段）
    for compound in pheno["compound"]:
        if "entity" not in compound or "name" not in compound["entity"]:
            continue
        if compound["entity"]["name"] != entity:
            continue
        if "logic" in compound and compound["logic"] != "and":
            raise DXCohortError(
                "Cannot create cohort: existing filter logic is not 'and'."
            )
        compound["filters"][entity_field] = [entity_field_filter]
        return filters

    # 尝试添加到已有同 entity 不同字段的过滤器
    for compound in pheno["compound"]:
        if "filters" not in compound:
            continue
        for other_ef in compound["filters"]:
            if other_ef.split("$")[0] != entity:
                continue
            if "logic" in compound and compound["logic"] != "and":
                continue
            compound["filters"][entity_field] = [entity_field_filter]
            return filters

    # 没有匹配的过滤器，创建新的
    pheno["compound"].append({
        "name": "phenotype",
        "logic": "and",
        "filters": {entity_field: [entity_field_filter]},
    })

    return filters


def build_cohort_filter_payload(
    ids: list[Any],
    entity: str,
    field: str,
    project: str,
    lambda_conv: Callable,
    base_sql: str | None = None,
) -> dict[str, Any]:
    """构建 cohort 的 pheno_filters payload。

    Args:
        ids: 已校验的 participant ID 列表。
        entity: 主键实体名。
        field: 主键字段名。
        project: 数据集所属项目 ID。
        lambda_conv: ID 类型转换函数。
        base_sql: 可选的 base SQL。

    Returns:
        包含 filters、project_context 的 payload dict。
    """
    filter_payload: dict[str, Any] = {
        "filters": {"logic": "and"},
        "project_context": project,
    }
    filter_payload["filters"] = _generate_pheno_filter(
        ids, entity, field, filter_payload["filters"], lambda_conv,
    )
    if "logic" not in filter_payload["filters"]:
        filter_payload["filters"]["logic"] = "and"
    if base_sql is not None:
        filter_payload["base_sql"] = base_sql

    return filter_payload


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
            f"Failed to generate cohort SQL: {e}", dx_error=e,
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

    Returns:
        传给 ``new_dxrecord()`` 的完整 payload。
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
    if base_sql:
        details["baseSql"] = base_sql
    if combined:
        details["combined"] = _cohort_combined_payload(combined)

    types = ["DatabaseQuery", "CohortBrowser"]
    if combined:
        types.append("CombinedDatabaseQuery")

    return {
        "name": name,
        "folder": folder,
        "project": project,
        "types": types,
        "details": details,
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
        record = new_dxrecord(**payload)
        return record.get_id()
    except Exception as e:
        raise DXCohortError(
            f"Failed to create cohort record: {e}", dx_error=e,
        ) from e
