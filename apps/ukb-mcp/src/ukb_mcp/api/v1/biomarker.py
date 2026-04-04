"""生物标志物 REST 端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ukb_mcp.api.deps import get_dx_client
from ukb_mcp.domain.biomarker.models import (
    BiomarkerField,
    BiomarkerQuery,
    BiomarkerStats,
)
from ukb_mcp.domain.biomarker.service import BiomarkerService
from dx_client import IDXClient

router = APIRouter(prefix="/biomarkers", tags=["biomarkers"])


def get_biomarker_service(dx_client: IDXClient = Depends(get_dx_client)) -> BiomarkerService:
    return BiomarkerService(dx_client)


@router.get("", response_model=list[BiomarkerField])
def list_biomarkers(
    entity: str | None = Query(default=None, description="按实体过滤，如 participant。"),
    name: str | None = Query(default=None, description="按字段名模糊匹配。"),
    refresh: bool = Query(default=False, description="强制刷新缓存。"),
    service: BiomarkerService = Depends(get_biomarker_service),
) -> list[BiomarkerField]:
    """列出可用的 biomarker 字段。

    从 UKB 数据字典中提取字段列表，返回 field_id / name / category / type。
    支持按实体和字段名过滤。
    """
    return service.list_fields(entity=entity, name_pattern=name, refresh=refresh)  # type: ignore[return-value]


@router.get("/{field_id}/stats", response_model=BiomarkerStats)
def get_biomarker_stats(
    field_id: str,
    refresh: bool = Query(default=False, description="强制刷新缓存。"),
    service: BiomarkerService = Depends(get_biomarker_service),
) -> BiomarkerStats:
    """获取指定字段的统计摘要。

    提取字段全部数据后计算 count / mean / std / min / max / median / missing_rate。
    仅适用于数值型字段。
    """
    return service.get_stats(field_id, refresh=refresh)  # type: ignore[return-value]


@router.post("/query")
def query_biomarkers(
    query: BiomarkerQuery,
    service: BiomarkerService = Depends(get_biomarker_service),
) -> list[dict]:
    """查询指定字段的值。

    按字段 ID 列表提取数据，支持分页。返回行字典列表，列名为 DX 字段名。
    """
    return service.query(query.fields, query.limit, query.offset, refresh=query.refresh)
