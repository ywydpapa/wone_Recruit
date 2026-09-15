import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import EMPLOYMENT_TYPES, COMPANY_SIZES, INDUSTRY_TYPES
from core.pagination import page_info, PER_PAGE

router = APIRouter()


@router.get("/companies", response_class=HTMLResponse)
async def mgr_companies(
    request: Request,
    q: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    company_size: Optional[str] = Query(None),
    sido: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT c.*, u.name AS user_name_val, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM companies c "
            "JOIN users u ON c.user_id = u.id "
            "LEFT JOIN regions r ON c.region_id = r.id "
            "WHERE c.approval_status = 'approved'"
        )
        params = []
        if q:
            sql += " AND (c.company_name LIKE ? OR c.biz_no LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if industry:
            sql += " AND c.industry=?"
            params.append(industry)
        if company_size:
            sql += " AND c.company_size=?"
            params.append(company_size)
        if sido:
            sql += " AND r.sido=?"
            params.append(sido)
        sql += " ORDER BY c.id"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        rows = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    companies = []
    for row in rows:
        d = dict(row)
        fac = d.get("accessibility_facilities") or "[]"
        try:
            d["facility_count"] = len(json.loads(fac))
        except (json.JSONDecodeError, TypeError):
            d["facility_count"] = 0
        companies.append(d)
    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if industry: qs_parts.append(f"industry={industry}")
    if company_size: qs_parts.append(f"company_size={company_size}")
    if sido: qs_parts.append(f"sido={sido}")
    return templates.TemplateResponse(
        request=request, name="manager/companies.html", context={
            "request": request, "page_title": "기업 목록",
            "user_name": user["name"], "user_role": "manager",
            "companies": companies,
            "company_sizes": COMPANY_SIZES,
            "industry_types": INDUSTRY_TYPES,
            "q": q or "",
            "selected_industry": industry or "",
            "selected_size": company_size or "",
            "selected_sido": sido or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/companies/{company_id}", response_class=HTMLResponse)
async def mgr_company_detail(request: Request, company_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        company = conn.execute(
            """SELECT c.*, r.sido AS region_sido, r.sigungu AS region_sigungu,
                      u.name AS account_name, u.phone AS account_phone, u.username AS account_email
               FROM companies c
               LEFT JOIN regions r ON c.region_id = r.id
               LEFT JOIN users u ON c.user_id = u.id
               WHERE c.id = ?""",
            (company_id,),
        ).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다.")
        active_jobs = conn.execute(
            "SELECT COUNT(*) FROM job_postings WHERE company_id=? AND status='open'", (company_id,)
        ).fetchone()[0]
        placed_count = conn.execute(
            "SELECT COUNT(*) FROM placements WHERE company_id=? AND end_date IS NULL", (company_id,)
        ).fetchone()[0]
        reviews = conn.execute(
            "SELECT id, rating, pros, cons, created_at FROM company_reviews WHERE company_id=? ORDER BY created_at DESC",
            (company_id,),
        ).fetchall()
        avg_rating = round(sum(r["rating"] for r in reviews) / len(reviews), 1) if reviews else None
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="manager/company_detail.html", context={
            "request": request, "page_title": f"기업 상세 - {company['company_name']}",
            "user_name": user["name"], "user_role": "manager",
            "company": company,
            "active_jobs": active_jobs,
            "placed_count": placed_count,
            "reviews": reviews,
            "avg_rating": avg_rating,
        }
    )


@router.get("/jobs", response_class=HTMLResponse)
async def mgr_jobs(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sido: Optional[str] = Query(None),
    employment_type: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT jp.*, c.company_name, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu, "
            "(SELECT COUNT(*) FROM candidacies ca WHERE ca.job_id=jp.id) AS applicant_count "
            "FROM job_postings jp "
            "JOIN companies c ON jp.company_id = c.id "
            "LEFT JOIN regions r ON jp.region_id = r.id "
            "WHERE 1=1"
        )
        params = []
        if q:
            sql += " AND (jp.title LIKE ? OR c.company_name LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if status:
            sql += " AND jp.status=?"
            params.append(status)
        if sido:
            sql += " AND r.sido=?"
            params.append(sido)
        if employment_type:
            sql += " AND jp.employment_type=?"
            params.append(employment_type)
        sql += " ORDER BY jp.created_at DESC"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        jobs = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if status: qs_parts.append(f"status={status}")
    if sido: qs_parts.append(f"sido={sido}")
    if employment_type: qs_parts.append(f"employment_type={employment_type}")
    return templates.TemplateResponse(
        request=request, name="manager/jobs.html", context={
            "request": request, "page_title": "공고 목록",
            "user_name": user["name"], "user_role": "manager",
            "jobs": jobs,
            "employment_types": EMPLOYMENT_TYPES,
            "q": q or "",
            "selected_status": status or "",
            "selected_sido": sido or "",
            "selected_type": employment_type or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def mgr_job_detail(request: Request, job_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        job = conn.execute(
            "SELECT jp.*, "
            "c.company_name, c.intro, c.industry, c.company_size, c.employee_count, "
            "c.disabled_count, c.website, c.accessibility_facilities, c.accessibility_note, "
            "c.hiring_experience, c.retention_note, c.logo_path, "
            "c.ceo, c.est_year, c.biz_type, c.address, "
            "jc.minor_name_ko AS category_name, jc.major_name_ko, "
            "jc.description AS category_description, jc.daily_tasks, jc.fit_notes, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM job_postings jp "
            "JOIN companies c ON jp.company_id=c.id "
            "LEFT JOIN job_categories jc ON jp.category_id=jc.id "
            "LEFT JOIN regions r ON jp.region_id=r.id "
            "WHERE jp.id=?",
            (job_id,),
        ).fetchone()
        if not job:
            return HTMLResponse(status_code=404)
        accommodations_provided = json.loads(job["accommodations_provided"]) if job["accommodations_provided"] else []
        preferred_disability = json.loads(job["preferred_disability"]) if job["preferred_disability"] else []
        applicant_count = conn.execute(
            "SELECT COUNT(*) FROM candidacies WHERE job_id=?", (job_id,)
        ).fetchone()[0]
        company_jobs = conn.execute(
            "SELECT jp.id, jp.title, jp.employment_type, jp.salary, jp.deadline, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM job_postings jp "
            "LEFT JOIN regions r ON jp.region_id=r.id "
            "WHERE jp.company_id=? AND jp.status='open' AND jp.id!=? "
            "ORDER BY jp.created_at DESC LIMIT 4",
            (job["company_id"], job_id),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/job_detail.html", context={
            "request": request, "page_title": job["title"],
            "user_name": user["name"], "user_role": "manager",
            "job": job,
            "accommodations_provided": accommodations_provided,
            "preferred_disability": preferred_disability,
            "seeker_needs": [],
            "is_bookmarked": False,
            "similar_jobs": [],
            "d_day": None,
            "already_applied": False,
            "company_jobs": company_jobs,
            "applicant_count": applicant_count,
        }
    )
