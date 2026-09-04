from fastapi import APIRouter
from routers.company import (
    profile, jobs, job_edit, applicants, applicant_actions,
    talents, calendar, recommendations, levy, attendance,
)

router = APIRouter()
for mod in [profile, jobs, job_edit, applicants, applicant_actions,
            talents, calendar, recommendations, levy, attendance]:
    router.include_router(mod.router)

api_router = talents.api_router
