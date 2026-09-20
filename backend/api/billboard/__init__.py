"""Billboard API router — mounts all billboard sub-routers."""

from fastapi import APIRouter, Depends, Query, Request, Response

from backend.api.billboard.data import _billboard_params
from backend.api.billboard.data import router as data_router
from backend.api.billboard.details import router as details_router
from backend.api.billboard.enrichment import router as enrichment_router
from backend.api.billboard.release_cycle import router as release_cycle_router
from backend.api.billboard.year_end import router as year_end_router
from backend.core.access_surface import public_readonly_db_guard_active
from backend.dependencies import BillboardFilters, MergeConfig
from backend.domains.billboard.persistent_cache import get_or_build_billboard_snapshot
from backend.models.snapshot import SnapshotUnavailableResponse

router = APIRouter(
    prefix="/billboard",
    tags=["Billboard"],
    responses={503: {"model": SnapshotUnavailableResponse}},
)


def require_public_detail_publication(
    request: Request,
    response: Response,
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
) -> None:
    """Gate detail/project/release views before their non-staged builders.

    These GETs can use raw frames in addition to the full chart publication.
    Checking here also covers a warm detail LRU and the project-only shortcut.
    Private maintenance and comparisons keep their existing computation path.
    """
    if request.method not in {"GET", "HEAD"} or not public_readonly_db_guard_active():
        return

    def no_build():
        raise AssertionError("public Billboard publication check cannot build")

    payload = get_or_build_billboard_snapshot(
        "full_data",
        {
            **_billboard_params(filters),
            "merge_level": merge.merge_level,
            "include_compilations": include_compilations,
        },
        no_build,
    )
    state = payload["snapshot"]
    response.headers["X-Snapshot-Freshness"] = state["freshness"]
    response.headers["X-Snapshot-Target-Revision"] = state["target_revision"]


router.include_router(data_router)
router.include_router(year_end_router)
router.include_router(
    release_cycle_router,
    prefix="/release-cycle",
    dependencies=[Depends(require_public_detail_publication)],
)
router.include_router(details_router, dependencies=[Depends(require_public_detail_publication)])
router.include_router(enrichment_router, prefix="/enrichment")
