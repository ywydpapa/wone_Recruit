import json
from typing import Optional
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import EMPLOYMENT_TYPES, ACCOMMODATION_OPTIONS

router = APIRouter(prefix="/company")


@router.get("/jobs/{job_id}/edit", response_class=HTMLResponse)
async def job_edit_form(request: Request, job_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        job = conn.execute(
            "SELECT * FROM job_postings WHERE id=? AND company_id=?",
            (job_id, company["id"])
        ).fetchone()
        categories = conn.execute("SELECT * FROM job_categories ORDER BY major_code, minor_code").fetchall()
        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
        selected_sido = ""
        if job and job["region_id"]:
            region_row = conn.execute("SELECT sido FROM regions WHERE id=?", (job["region_id"],)).fetchone()
            if region_row:
                selected_sido = region_row["sido"]
        accommodations_provided = json.loads(job["accommodations_provided"]) if job and job["accommodations_provided"] else []
        preferred_disability = json.loads(job["preferred_disability"]) if job and job["preferred_disability"] else []
    finally:
        conn.close()
    if job is None:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    return templates.TemplateResponse(
        request=request, name="company/job_form.html", context={
            "request": request, "page_title": "공고 수정",
            "user_name": user["user_name"], "user_role": "company",
            "job": job,
            "selected_sido": selected_sido,
            "employment_types": EMPLOYMENT_TYPES,
            "categories": categories,
            "accommodation_options": ACCOMMODATION_OPTIONS,
            "disability_types": disability_types,
            "daily_hours_options": [4, 6, 8],
            "accommodations_provided": accommodations_provided,
            "preferred_disability": preferred_disability,
        }
    )


@router.post("/jobs/{job_id}/edit")
async def job_update(
    request: Request,
    job_id: int,
    title: str = Form(...),
    category_id: Optional[int] = Form(None),
    region_id: int = Form(None),
    employment_type: str = Form("정규직"),
    remote_available: str = Form("0"),
    work_start_time: str = Form("09:00"),
    work_end_time: str = Form("18:00"),
    work_days: str = Form("월~금"),
    flexible_hours: str = Form("0"),
    accommodations_note: str = Form(""),
    preferred_severity: str = Form("무관"),
    min_work_hours: int = Form(8),
    benefits: str = Form(""),
    requirements: str = Form(""),
    salary: str = Form(""),
    deadline: str = Form(""),
    description: str = Form(""),
    status: str = Form("draft"),
):
    user = require_role(request, "company")
    form = await request.form()
    remote_val = 1 if remote_available in ("1", "on", "true") else 0
    flexible_val = 1 if flexible_hours in ("1", "on", "true") else 0
    accommodations_provided = json.dumps(form.getlist("accommodations_provided"), ensure_ascii=False)
    preferred_disability = json.dumps(form.getlist("preferred_disability"), ensure_ascii=False)
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        conn.execute(
            """UPDATE job_postings SET
               title=?, category_id=?, region_id=?, employment_type=?, remote_available=?,
               work_start_time=?, work_end_time=?, work_days=?, flexible_hours=?,
               accommodations_provided=?, accommodations_note=?,
               preferred_disability=?, preferred_severity=?, min_work_hours=?,
               benefits=?, requirements=?,
               salary=?, deadline=?, description=?, status=?
               WHERE id=? AND company_id=?""",
            (title, category_id, region_id, employment_type, remote_val,
             work_start_time, work_end_time, work_days, flexible_val,
             accommodations_provided, accommodations_note,
             preferred_disability, preferred_severity, min_work_hours,
             benefits, requirements,
             salary, deadline, description, status,
             job_id, company["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/jobs", status_code=303)
