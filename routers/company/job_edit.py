import json
from typing import Optional
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import EMPLOYMENT_TYPES, ACCOMMODATION_OPTIONS

router = APIRouter(prefix="/company")


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        job = conn.execute(
            """SELECT jp.*,
                      c.company_name,
                      jc.minor_name_ko AS category_name, jc.major_name_ko,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM job_postings jp
               JOIN companies c ON jp.company_id=c.id
               LEFT JOIN job_categories jc ON jp.category_id=jc.id
               LEFT JOIN regions r ON jp.region_id=r.id
               WHERE jp.id=? AND jp.company_id=?""",
            (job_id, company["id"]),
        ).fetchone()
        applicant_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM applications WHERE job_id=?", (job_id,)
        ).fetchone()["cnt"]
    finally:
        conn.close()
    if not job:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    accommodations_provided = json.loads(job["accommodations_provided"]) if job["accommodations_provided"] else []
    preferred_disability = json.loads(job["preferred_disability"]) if job["preferred_disability"] else []
    return templates.TemplateResponse(
        request=request, name="company/job_detail.html", context={
            "request": request, "page_title": job["title"],
            "user_name": user["name"], "user_role": "company",
            "job": job,
            "applicant_count": applicant_count,
            "accommodations_provided": accommodations_provided,
            "preferred_disability": preferred_disability,
        }
    )


@router.get("/jobs/{job_id}/edit", response_class=HTMLResponse)
async def job_edit_form(request: Request, job_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["id"],)).fetchone()
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
            "user_name": user["name"], "user_role": "company",
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
    qualifications: str = Form(""),
    preferred: str = Form(""),
    tasks: str = Form(""),
    tools: str = Form(""),
    experience_level: str = Form("무관"),
    education: str = Form(""),
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
    hiring_process = form.get("hiring_process", "")
    headcount = form.get("headcount", "")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        set_status = "pending_review" if status == "open" else status
        conn.execute(
            """UPDATE job_postings SET
               title=?, category_id=?, region_id=?, employment_type=?, remote_available=?,
               work_start_time=?, work_end_time=?, work_days=?, flexible_hours=?,
               accommodations_provided=?, accommodations_note=?,
               preferred_disability=?, preferred_severity=?, min_work_hours=?,
               benefits=?, qualifications=?, preferred=?,
               tasks=?, tools=?, experience_level=?, education=?,
               hiring_process=?, headcount=?,
               salary=?, deadline=?, description=?, status=?,
               rejection_reason=CASE WHEN ? THEN '' ELSE rejection_reason END
               WHERE id=? AND company_id=?""",
            (title, category_id, region_id, employment_type, remote_val,
             work_start_time, work_end_time, work_days, flexible_val,
             accommodations_provided, accommodations_note,
             preferred_disability, preferred_severity, min_work_hours,
             benefits, qualifications, preferred,
             tasks, tools, experience_level, education,
             hiring_process, headcount,
             salary, deadline, description, set_status,
             1 if set_status == "pending_review" else 0,
             job_id, company["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/company/jobs/{job_id}", status_code=303)


@router.get("/jobs/{job_id}/preview", response_class=HTMLResponse)
async def job_preview(request: Request, job_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        job = conn.execute(
            """SELECT jp.*,
                      c.company_name, c.intro, c.industry, c.company_size, c.employee_count,
                      c.disabled_count, c.website, c.accessibility_facilities, c.accessibility_note,
                      c.hiring_experience, c.retention_note, c.logo_path,
                      c.ceo, c.est_year, c.biz_type, c.address,
                      jc.minor_name_ko AS category_name, jc.major_name_ko,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM job_postings jp
               JOIN companies c ON jp.company_id=c.id
               LEFT JOIN job_categories jc ON jp.category_id=jc.id
               LEFT JOIN regions r ON jp.region_id=r.id
               WHERE jp.id=? AND jp.company_id=?""",
            (job_id, company["id"]),
        ).fetchone()
    finally:
        conn.close()
    if not job:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    accommodations_provided = json.loads(job["accommodations_provided"]) if job["accommodations_provided"] else []
    preferred_disability = json.loads(job["preferred_disability"]) if job["preferred_disability"] else []
    return templates.TemplateResponse(
        request=request, name="company/job_preview.html", context={
            "request": request, "page_title": f"[미리보기] {job['title']}",
            "user_name": user["name"], "user_role": "company",
            "job": job,
            "accommodations_provided": accommodations_provided,
            "preferred_disability": preferred_disability,
        }
    )
