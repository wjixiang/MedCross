"""DNAnexus vizserver REST API 客户端。

封装所有与 vizserver 交互的 HTTP 调用，通过依赖注入便于测试。
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

import dxpy
from dxpy.exceptions import DXAPIError as DxPyDXAPIError
from dxpy.exceptions import DXError as DxPyDXError

from .dx_exceptions import (
    DXCohortError,
    DXVizserverError,
    translate_dx_error,
    check_vizserver_response,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class IVizserverClient(Protocol):
    """DNAnexus vizserver REST API 交互协议。

    实现类封装 vizserver 资源 URL 的构建和 ``dxpy.DXHTTPRequest`` 的调用，
    使所有 vizserver 调用可注入和可 mock。
    """

    def get_visualize_info(
        self, record_id: str, project: str,
    ) -> dict[str, Any]:
        """调用 ``/{record_id}/visualize`` 获取 vizserver 连接信息。

        校验 datasetVersion == "3.0" 和 recordTypes 后返回。

        Args:
            record_id: Dataset 或 CohortBrowser 的 record ID。
            project: 所属项目 ID。

        Returns:
            vizserver 响应 dict（url、dataset、databases、schema 等）。

        Raises:
            DXCohortError: record 无效、版本不支持或权限不足。
        """
        ...

    def query_raw_data(
        self,
        viz_info: dict[str, Any],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """调用 ``{url}/data/3.0/{dataset}/raw`` 查询数据。

        统一的字段提取端点，用于字段提取、ID 校验和 cohort 字段提取。

        Args:
            viz_info: ``get_visualize_info()`` 的返回值。
            payload: 请求体，包含 project_context、fields 及可选的 filters/base_sql。

        Returns:
            结果列表（响应中的 ``"results"`` 键）。

        Raises:
            DXAPIError: vizserver 请求失败。
        """
        ...

    def generate_cohort_sql(
        self,
        viz_info: dict[str, Any],
        filter_payload: dict[str, Any],
    ) -> str:
        """调用 ``{url}/viz-query/3.0/{dataset}/raw-cohort-query`` 生成 cohort SQL。

        Args:
            viz_info: ``get_visualize_info()`` 的返回值。
            filter_payload: 包含 project_context 和 filters 的 payload。

        Returns:
            生成的 SQL 字符串（末尾带分号）。

        Raises:
            DXVizserverError: vizserver 返回错误响应。
            DXCohortError: vizserver 请求失败。
        """
        ...

    @abstractmethod
    def generate_sql(
        self,
        viz_info: dict[str, Any],
        payload: dict[str, Any],
    ) -> str:
        """调用 ``{url}/viz-query/3.0/{dataset}/raw-query`` 生成通用 SQL。

        与 ``generate_cohort_sql`` 不同，此端点接受任意 filters/raw_filters 组合，
        不限于 cohort 的 pheno_filters 结构。

        Args:
            viz_info: ``get_visualize_info()`` 的返回值。
            payload: 请求体，包含 project_context、fields 及可选的 filters/raw_filters。

        Returns:
            生成的 SQL 字符串。

        Raises:
            DXVizserverError: vizserver 返回错误响应。
            DXAPIError: HTTP 请求失败。
        """
        ...


class VizserverClient:
    """``IVizserverClient`` 的默认实现，使用 ``dxpy`` SDK。

    整个代码库中唯一构建 vizserver 资源 URL 并调用
    ``dxpy.DXHTTPRequest(prepend_srv=False)`` 的地方。
    """

    def get_visualize_info(
        self, record_id: str, project: str,
    ) -> dict[str, Any]:
        """调用 ``/{record_id}/visualize`` 获取 vizserver 连接信息。"""
        try:
            resp = dxpy.DXHTTPRequest(
                "/%s/visualize" % record_id,
                {"project": project, "cohortBrowser": False},
            )
        except Exception as e:
            raise DXCohortError(
                f"Failed to get visualize info for '{record_id}': {e}",
                dx_error=e,
            ) from e

        check_vizserver_response(
            resp, f"Failed to get visualize info for '{record_id}'",
        )

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

    def query_raw_data(
        self,
        viz_info: dict[str, Any],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """调用 ``{url}/data/3.0/{dataset}/raw`` 查询数据。"""
        resource = (
            viz_info["url"] + "/data/3.0/" + viz_info["dataset"] + "/raw"
        )
        try:
            resp = dxpy.DXHTTPRequest(
                resource=resource, data=payload, prepend_srv=False,
            )
        except (DxPyDXError, DxPyDXAPIError) as e:
            translate_dx_error(
                e,
                f"vizserver data query failed for dataset '{viz_info['dataset']}'",
            )
            raise  # unreachable after translate_dx_error

        check_vizserver_response(
            resp, f"vizserver data query failed for dataset '{viz_info['dataset']}'",
        )

        if "sql" in resp and "results" not in resp:
            logger.warning(
                "query_raw_data received a SQL response (return_query=True in payload?). "
                "Use generate_sql() for SQL generation. Returning empty list."
            )

        return resp.get("results", [])

    def generate_cohort_sql(
        self,
        viz_info: dict[str, Any],
        filter_payload: dict[str, Any],
    ) -> str:
        """调用 ``{url}/viz-query/3.0/{dataset}/raw-cohort-query`` 生成 cohort SQL。"""
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
        except (DxPyDXError, DxPyDXAPIError) as e:
            translate_dx_error(
                e,
                f"vizserver cohort SQL generation failed for dataset '{viz_info['dataset']}'",
            )
            raise  # unreachable after translate_dx_error

        check_vizserver_response(
            resp, f"vizserver cohort SQL generation failed for dataset '{viz_info['dataset']}'",
        )

        return resp["sql"] + ";"

    def generate_sql(
        self,
        viz_info: dict[str, Any],
        payload: dict[str, Any],
    ) -> str:
        """调用 ``{url}/viz-query/3.0/{dataset}/raw-query`` 生成通用 SQL。"""
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
        except (DxPyDXError, DxPyDXAPIError) as e:
            translate_dx_error(
                e,
                f"vizserver SQL generation failed for dataset '{viz_info['dataset']}'",
            )
            raise  # unreachable after translate_dx_error

        check_vizserver_response(
            resp, f"vizserver raw-query failed for dataset '{viz_info['dataset']}'",
        )

        return resp["sql"]
