"""字段字典 REST 端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import TypeAdapter

from ukb_mcp.domain.field.models import FieldDictItem, FieldDictResponse
from ukb_mcp.service.fieldStorageService import FieldStorageService, get_field_storage

router = APIRouter(prefix="/field", tags=["field"])

_field_adapter = TypeAdapter(list[FieldDictItem])


@router.get("/list", response_model=FieldDictResponse)
def list_fields(
    page: int = Query(default=1, ge=1, description="页码。"),
    page_size: int = Query(default=100, ge=1, le=1000, description="每页条数。"),
    storage: FieldStorageService = Depends(get_field_storage),
):
    df = storage.list_fields(page, page_size)
    return FieldDictResponse(
        total=len(df),
        page=page,
        page_size=page_size,
        data=_field_adapter.validate_python(df.to_dict(orient="records")),
    )


@router.get("/query", response_model=FieldDictResponse)
def query_fields(
    condition: str = Query(description="查询条件，如: entity = 'participant' AND type = 'string'"),
    page: int = Query(default=1, ge=1, description="页码。"),
    page_size: int = Query(default=100, ge=1, le=1000, description="每页条数。"),
    storage: FieldStorageService = Depends(get_field_storage),
):
    df = storage.query_fields(condition, page, page_size)
    return FieldDictResponse(
        total=len(df),
        page=page,
        page_size=page_size,
        data=_field_adapter.validate_python(df.to_dict(orient="records")),
    )
