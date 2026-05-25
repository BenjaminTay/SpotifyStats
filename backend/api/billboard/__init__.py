"""Billboard API router — mounts all billboard sub-routers."""

from fastapi import APIRouter

from backend.api.billboard.data import router as data_router
from backend.api.billboard.release_cycle import router as release_cycle_router

router = APIRouter(prefix="/billboard", tags=["Billboard"])

router.include_router(data_router)
router.include_router(release_cycle_router, prefix="/release-cycle")
