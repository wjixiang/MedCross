"""关联查询 REST 端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ukb_mcp.api.deps import get_dx_client
from ukb_mcp.domain.association.models import AssociationQuery
from ukb_mcp.domain.association.service import AssociationService
from ukb_mcp.infra import IDXClient

router = APIRouter(prefix="/association", tags=["association"])


def get_association_service(
    dx_client: IDXClient = Depends(get_dx_client),
) -> AssociationService:
    return AssociationService(dx_client)


@router.post("/query")
def query_association(
    query: AssociationQuery,
    service: AssociationService = Depends(get_association_service),
) -> list[dict]:
    """查询 biomarker 与结局的关联。"""
    return service.query(query.biomarker_id, query.outcome_id, query.limit)
