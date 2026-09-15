from fastapi import APIRouter
from . import dashboard, caseload, consultations, matching, placements, views

router = APIRouter(prefix="/mgr")
router.include_router(dashboard.router)
router.include_router(caseload.router)
router.include_router(consultations.router)
router.include_router(matching.router)
router.include_router(placements.router)
router.include_router(views.router)
