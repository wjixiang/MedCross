"""生物标志物 REST 端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ukb_mcp.api.deps import get_dx_client
from ukb_mcp.domain.biomarker.models import BiomarkerQuery, BiomarkerStats
from ukb_mcp.domain.biomarker.service import BiomarkerService
from dx_client import IDXClient

router = APIRouter(prefix="/biomarkers", tags=["biomarkers"])


def get_biomarker_service(dx_client: IDXClient = Depends(get_dx_client)) -> BiomarkerService:
    return BiomarkerService(dx_client)


@router.get("")
def list_biomarkers(
    entity: str | None = Query(default=None, description="按实体过滤，如 participant。"),
    name: str | None = Query(default=None, description="按字段名模糊匹配。"),
    refresh: bool = Query(default=False, description="强制刷新缓存。"),
    service: BiomarkerService = Depends(get_biomarker_service),
) -> list[dict]:
    """列出可用的 biomarker 字段。"""
    return service.list_fields(entity=entity, name_pattern=name, refresh=refresh)


@router.get("/{field_id}/stats", response_model=BiomarkerStats)
def get_biomarker_stats(
    field_id: str,
    refresh: bool = Query(default=False, description="强制刷新缓存。"),
    service: BiomarkerService = Depends(get_biomarker_service),
) -> BiomarkerStats:
    """获取指定字段的统计摘要。"""
    return service.get_stats(field_id, refresh=refresh)  # type: ignore[return-value]


@router.post("/query")
def query_biomarkers(
    query: BiomarkerQuery,
    service: BiomarkerService = Depends(get_biomarker_service),
) -> list[dict]:
    """查询指定字段的值。"""
    return service.query(query.fields, query.limit, query.offset, refresh=query.refresh)
