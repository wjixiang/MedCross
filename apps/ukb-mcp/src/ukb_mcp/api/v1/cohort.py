"""队列 REST 端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ukb_mcp.api.deps import get_dx_client
from ukb_mcp.domain.cohort.models import (
    CohortCreateRequest,
    CohortDetail,
    CohortInfo,
    CohortListItem,
    ExtractFieldsRequest,
)
from ukb_mcp.domain.cohort.service import CohortService
from dx_client import IDXClient

router = APIRouter(prefix="/cohort", tags=["cohort"])


def get_cohort_service(dx_client: IDXClient = Depends(get_dx_client)) -> CohortService:
    return CohortService(dx_client)


@router.get("/", response_model=list[CohortListItem])
def list_cohorts(
    name: str | None = Query(default=None, description="名称匹配模式。"),
    limit: int = Query(default=100, ge=1, le=1000),
    refresh: bool = Query(default=False),
    service: CohortService = Depends(get_cohort_service),
) -> list[CohortListItem]:
    """列出当前项目中的队列。"""
    records = service.list_cohorts(name_pattern=name, limit=limit, refresh=refresh)
    return [
        CohortListItem(
            id=r.id,
            name=r.name,
            project=r.project,
            state=r.state,
            created=r.created,
            modified=r.modified,
        )
        for r in records
    ]


@router.get("/find", response_model=CohortDetail)
def find_cohort(
    name: str | None = Query(default=None, description="名称匹配模式。"),
    refresh: bool = Query(default=False),
    service: CohortService = Depends(get_cohort_service),
) -> CohortDetail:
    """按名称查找队列，返回第一个匹配项。"""
    record = service.find_cohort(name_pattern=name, refresh=refresh)
    return CohortDetail(
        id=record.id,
        name=record.name,
        project=record.project,
        state=record.state,
        created=record.created,
        modified=record.modified,
        details=record.details,
    )


@router.post("/", response_model=CohortInfo)
def create_cohort(
    req: CohortCreateRequest,
    service: CohortService = Depends(get_cohort_service),
) -> CohortInfo:
    """基于筛选条件创建队列。"""
    info = service.create_cohort(
        name=req.name,
        filters=req.filters,
        dataset_ref=req.dataset_ref,
        folder=req.folder,
        description=req.description,
        entity_fields=req.entity_fields or None,
    )
    return CohortInfo(
        id=info.id,
        name=info.name,
        project=info.project,
        folder=info.folder,
        state=info.state,
        description=info.description,
        created=info.created,
        modified=info.modified,
        participant_count=info.participant_count,
        entity_fields=info.entity_fields,
    )


@router.get("/{cohort_id}", response_model=CohortDetail)
def get_cohort_info(
    cohort_id: str,
    refresh: bool = Query(default=False),
    service: CohortService = Depends(get_cohort_service),
) -> CohortDetail:
    """获取队列详情。"""
    record = service.get_cohort(cohort_id, refresh=refresh)
    return CohortDetail(
        id=record.id,
        name=record.name,
        project=record.project,
        state=record.state,
        created=record.created,
        modified=record.modified,
        details=record.details,
    )


@router.delete("/{cohort_id}", status_code=204)
def delete_cohort(
    cohort_id: str,
    service: CohortService = Depends(get_cohort_service),
) -> None:
    """删除队列。"""
    service.delete_cohort(cohort_id)


@router.post("/{cohort_id}/extract")
def extract_cohort_fields(
    cohort_id: str,
    req: ExtractFieldsRequest,
    service: CohortService = Depends(get_cohort_service),
) -> list[dict]:
    """提取队列内参与者的指定字段数据。"""
    return service.extract_fields(cohort_id, req.entity_fields, refresh=req.refresh)
