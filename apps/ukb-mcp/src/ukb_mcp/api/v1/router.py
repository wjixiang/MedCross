"""v1 API 路由聚合。"""

from fastapi import APIRouter

from .cohort import router as cohort_router
from .association import router as association_router
from .export import router as export_router
from .database import router as database_router
from .field import router as field_router
from .manage import router as manage_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(cohort_router)
v1_router.include_router(association_router)
v1_router.include_router(export_router)
v1_router.include_router(database_router)
v1_router.include_router(field_router)
v1_router.include_router(manage_router)
