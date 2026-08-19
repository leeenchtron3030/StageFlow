from fastapi import APIRouter

from app.api.v1.demo import router as demo_router
from app.api.v1.health import router as health_router
from app.api.v1.kernel_status import router as kernel_status_router
from app.api.v1.media_timing_evidence import router as media_timing_evidence_router

router = APIRouter()
router.include_router(health_router)
router.include_router(demo_router)
router.include_router(kernel_status_router)
router.include_router(media_timing_evidence_router)
