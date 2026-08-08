from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.kernel_status import router as kernel_status_router

router = APIRouter()
router.include_router(health_router)
router.include_router(kernel_status_router)
