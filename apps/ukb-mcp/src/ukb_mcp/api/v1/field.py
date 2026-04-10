"""字段字典 REST 端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ukb_mcp.service.fieldStorageService import FieldStorageService, get_field_storage

router = APIRouter(prefix="/field", tags=["field"])


@router.get("/list_field")
def list_fields(
    page: int = Query(default=1, ge=1, description="页码。"),
    page_size: int = Query(default=100, ge=1, le=1000, description="每页条数。"),
    storage: FieldStorageService = Depends(get_field_storage),
):
    return storage.list_fields(page, page_size)
