"""队列 REST 端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ukb_mcp.api.deps import get_dx_client
from ukb_mcp.domain.cohort.models import CohortFilter, CohortInfo
from ukb_mcp.domain.cohort.service import CohortService
from dx_client import IDXClient

router = APIRouter(prefix="/cohort", tags=["cohort"])


def get_cohort_service(dx_client: IDXClient = Depends(get_dx_client)) -> CohortService:
    return CohortService(dx_client)


@router.post("/filter")
def filter_cohort(
    filters: CohortFilter,
    service: CohortService = Depends(get_cohort_service),
) -> list[dict]:
    """按条件筛选参与者构建队列。"""
    return service.filter(filters.biomarker_ranges, filters.limit, filters.offset)


@router.get("/{cohort_id}", response_model=CohortInfo)
def get_cohort_info(
    cohort_id: str,
    service: CohortService = Depends(get_cohort_service),
) -> CohortInfo:
    """获取队列详情。"""
    return service.get_info(cohort_id)  # type: ignore[return-value]
