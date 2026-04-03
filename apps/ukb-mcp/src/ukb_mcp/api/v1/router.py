"""v1 API 路由聚合。"""

from fastapi import APIRouter

from .biomarker import router as biomarker_router
from .cohort import router as cohort_router
from .association import router as association_router
from .export import router as export_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(biomarker_router)
v1_router.include_router(cohort_router)
v1_router.include_router(association_router)
v1_router.include_router(export_router)
