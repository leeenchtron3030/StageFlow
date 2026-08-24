from fastapi import APIRouter, Depends

from app.api.authentication import require_api_secret
from app.api.v1.demo import router as demo_router
from app.api.v1.editorial import router as editorial_router
from app.api.v1.health import router as health_router
from app.api.v1.kernel_status import router as kernel_status_router
from app.api.v1.media_timing_evidence import router as media_timing_evidence_router
from app.api.v1.work_queue import router as work_queue_router

router = APIRouter()
router.include_router(health_router)
_protected_dependencies = [Depends(require_api_secret)]
router.include_router(demo_router, dependencies=_protected_dependencies)
router.include_router(editorial_router, dependencies=_protected_dependencies)
router.include_router(kernel_status_router, dependencies=_protected_dependencies)
router.include_router(media_timing_evidence_router, dependencies=_protected_dependencies)
router.include_router(work_queue_router, dependencies=_protected_dependencies)
