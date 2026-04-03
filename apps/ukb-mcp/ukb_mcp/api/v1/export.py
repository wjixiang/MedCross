"""数据导出 REST 端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_dx_client
from domain.export.models import ExportRequest
from domain.export.service import ExportService
from infra import IDXClient

router = APIRouter(prefix="/export", tags=["export"])


def get_export_service(dx_client: IDXClient = Depends(get_dx_client)) -> ExportService:
    return ExportService(dx_client)


@router.post("/csv")
def export_csv(
    request: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> dict:
    """导出数据为 CSV 文件。"""
    path = service.to_csv(request.fields, request.cohort_id)
    return {"format": "csv", "path": str(path)}


@router.post("/parquet")
def export_parquet(
    request: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> dict:
    """导出数据为 Parquet 文件。"""
    path = service.to_parquet(request.fields, request.cohort_id)
    return {"format": "parquet", "path": str(path)}
