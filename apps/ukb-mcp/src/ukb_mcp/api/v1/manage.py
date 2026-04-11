from dx_client import IDXClient
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ukb_mcp.api.deps import get_dx_client
from ukb_mcp.service.fieldStorageService import get_field_storage

router = APIRouter(prefix="/manage")


class FieldDictSyncResponse(BaseModel):
    success: bool


@router.get("/update_field_dict", response_model=FieldDictSyncResponse)
def get_field_dict(dxclient: IDXClient = Depends(get_dx_client)):
    storage = get_field_storage(dx_client=dxclient)
    storage.sync_field_dict()
    return FieldDictSyncResponse(success=True)
