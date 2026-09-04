import json
from typing import Optional
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import EMPLOYMENT_TYPES, ACCOMMODATION_OPTIONS
from core.pagination import page_info, PER_PAGE

router = APIRouter(prefix="/company")


@router.get("/jobs", response_class=HTMLResponse)
async def job_list(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = 1,
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        where = ["jp.company_id=?"]
        params = [company["id"]]
        if q and q.strip():
            where.append("jp.title LIKE ?")
            params.append(f"%{q.strip()}%")
        if status and status in ("open", "draft", "closed", "filled"):
            where.append("jp.status=?")
            params.append(status)
        sql = f"""SELECT jp.*, r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM job_postings jp
               LEFT JOIN regions r ON jp.region_id = r.id
               WHERE {' AND '.join(where)} ORDER BY jp.created_at DESC"""
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        jobs = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
        qs_parts = []
        if q:
            qs_parts.append(f"q={q}")
        if status:
            qs_parts.append(f"status={status}")
        base_qs = "&".join(qs_parts)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/jobs.html", context={
            "request": request, "page_title": "공고 관리",
            "user_name": user["user_name"], "user_role": "company",
            "jobs": jobs, "q": q or "", "selected_status": status or "",
            "pagination": pagination, "base_qs": base_qs,
        }
    )


@router.get("/jobs/new", response_class=HTMLResponse)
async def job_new_form(request: Request):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        categories = conn.execute("SELECT * FROM job_categories ORDER BY major_code, minor_code").fetchall()
        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/job_form.html", context={
            "request": request, "page_title": "새 공고 작성",
            "user_name": user["user_name"], "user_role": "company",
            "job": None,
            "selected_sido": "",
            "employment_types": EMPLOYMENT_TYPES,
            "categories": categories,
            "accommodation_options": ACCOMMODATION_OPTIONS,
            "disability_types": disability_types,
            "daily_hours_options": [4, 6, 8],
            "accommodations_provided": [],
            "preferred_disability": [],
        }
    )


@router.post("/jobs/new")
async def job_create(
    request: Request,
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
            """INSERT INTO job_postings
               (company_id, title, category_id, region_id, employment_type, remote_available,
                work_start_time, work_end_time, work_days, flexible_hours,
                accommodations_provided, accommodations_note,
                preferred_disability, preferred_severity, min_work_hours,
                benefits, requirements,
                salary, deadline, description, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (company["id"], title, category_id, region_id, employment_type, remote_val,
             work_start_time, work_end_time, work_days, flexible_val,
             accommodations_provided, accommodations_note,
             preferred_disability, preferred_severity, min_work_hours,
             benefits, requirements,
             salary, deadline, description, status),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/jobs", status_code=303)


@router.post("/jobs/{job_id}/copy")
async def job_copy(request: Request, job_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        job = conn.execute("SELECT * FROM job_postings WHERE id=? AND company_id=?", (job_id, company["id"])).fetchone()
        if not job:
            return RedirectResponse(url="/company/jobs", status_code=303)
        conn.execute(
            """INSERT INTO job_postings
               (company_id, title, category_id, region_id, employment_type, remote_available,
                work_start_time, work_end_time, work_days, flexible_hours, salary, deadline,
                accommodations_provided, accommodations_note,
                preferred_disability, preferred_severity, min_work_hours,
                benefits, requirements, description, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (company["id"], job["title"] + " (복사)", job["category_id"], job["region_id"],
             job["employment_type"], job["remote_available"],
             job["work_start_time"], job["work_end_time"], job["work_days"], job["flexible_hours"],
             job["salary"], job["deadline"],
             job["accommodations_provided"], job["accommodations_note"],
             job["preferred_disability"], job["preferred_severity"], job["min_work_hours"],
             job["benefits"], job["requirements"], job["description"], "draft"),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/jobs", status_code=303)


@router.post("/jobs/{job_id}/status")
async def job_status_change(
    request: Request,
    job_id: int,
    status: str = Form(...),
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        conn.execute(
            "UPDATE job_postings SET status=? WHERE id=? AND company_id=?",
            (status, job_id, company["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/jobs", status_code=303)
