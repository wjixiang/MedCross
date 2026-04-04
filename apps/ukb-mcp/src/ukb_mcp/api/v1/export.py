"""数据导出 REST 端点。"""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ukb_mcp.api.deps import get_dx_client
from ukb_mcp.domain.export.models import ExportRequest
from ukb_mcp.domain.export.service import ExportService
from dx_client import IDXClient

router = APIRouter(prefix="/export", tags=["export"])


def get_export_service(dx_client: IDXClient = Depends(get_dx_client)) -> ExportService:
    return ExportService(dx_client)


@router.post("/csv")
def export_csv(
    request: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> StreamingResponse:
    """导出数据为 CSV 文件。"""
    df = service.query(request.fields, request.cohort_id, refresh=request.refresh)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export.csv"},
    )


@router.post("/parquet")
def export_parquet(
    request: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> StreamingResponse:
    """导出数据为 Parquet 文件。"""
    df = service.query(request.fields, request.cohort_id, refresh=request.refresh)
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=export.parquet"},
    )
