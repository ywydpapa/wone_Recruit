import json
import calendar
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import EMPLOYMENT_TYPES, STATUS_LABELS, ACCOMMODATION_OPTIONS, COMPANY_SIZES, INDUSTRY_TYPES
from core.candidacy import apply_transition, TRANSITIONS, TERMINAL
from core.levy import calc_levy
from core.upload import save_upload
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification

router = APIRouter(prefix="/company")
api_router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
async def company_profile_form(request: Request, success: str = ""):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        selected_sido = ""
        accessibility_facilities = []
        if company:
            if company["region_id"]:
                region_row = conn.execute("SELECT sido FROM regions WHERE id=?", (company["region_id"],)).fetchone()
                if region_row:
                    selected_sido = region_row["sido"]
            if company["accessibility_facilities"]:
                accessibility_facilities = json.loads(company["accessibility_facilities"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/profile_form.html", context={
            "request": request, "page_title": "기업 정보",
            "user_name": user["user_name"], "user_role": "company",
            "company": company, "success": success,
            "selected_sido": selected_sido,
            "company_sizes": COMPANY_SIZES,
            "industry_types": INDUSTRY_TYPES,
            "accommodation_options": ACCOMMODATION_OPTIONS,
            "accessibility_facilities": accessibility_facilities,
        }
    )


@router.post("/profile")
async def company_profile_save(
    request: Request,
    company_name: str = Form(...),
    biz_no: str = Form(""),
    industry: str = Form(""),
    employee_count: int = Form(0),
    disabled_count: int = Form(0),
    region_id: int = Form(None),
    intro: str = Form(""),
    website: str = Form(""),
    company_size: str = Form(""),
    accessibility_note: str = Form(""),
    hiring_experience: str = Form("0"),
    retention_note: str = Form(""),
    benefits: str = Form(""),
    logo: Optional[UploadFile] = File(None),
):
    user = require_role(request, "company")
    form = await request.form()
    hiring_exp_val = 1 if hiring_experience in ("1", "on", "true") else 0
    accessibility_facilities = json.dumps(form.getlist("accessibility_facilities"), ensure_ascii=False)

    logo_path = ""
    if logo and logo.filename:
        logo_path = await save_upload(
            logo, "logos", user["user_id"],
            ["image/jpeg", "image/png", "image/webp"], 5 * 1024 * 1024,
        )

    conn = get_sqlite()
    try:
        existing = conn.execute("SELECT id, logo_path FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not logo_path and existing:
            logo_path = existing["logo_path"] or ""
        if existing:
            conn.execute("""UPDATE companies SET
                company_name=?, biz_no=?, industry=?, employee_count=?, disabled_count=?,
                region_id=?, intro=?, website=?, company_size=?,
                accessibility_facilities=?, accessibility_note=?,
                hiring_experience=?, retention_note=?, benefits=?, logo_path=?,
                updated_at=datetime('now','localtime')
                WHERE user_id=?""",
                (company_name, biz_no, industry, employee_count, disabled_count,
                 region_id, intro, website, company_size,
                 accessibility_facilities, accessibility_note,
                 hiring_exp_val, retention_note, benefits, logo_path,
                 user["user_id"]))
        else:
            conn.execute("""INSERT INTO companies
                (user_id, company_name, biz_no, industry, employee_count, disabled_count,
                 region_id, intro, website, company_size,
                 accessibility_facilities, accessibility_note,
                 hiring_experience, retention_note, benefits, logo_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (user["user_id"], company_name, biz_no, industry, employee_count, disabled_count,
                 region_id, intro, website, company_size,
                 accessibility_facilities, accessibility_note,
                 hiring_exp_val, retention_note, benefits, logo_path))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/profile?success=1", status_code=303)


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


@router.get("/levy", response_class=HTMLResponse)
async def company_levy(request: Request):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        rates_rows = conn.execute("SELECT rate_type, amount FROM levy_rates WHERE year=2026").fetchall()
        rates = {r["rate_type"]: r["amount"] for r in rates_rows}
    finally:
        conn.close()

    result = calc_levy(company["employee_count"], company["disabled_count"], rates)

    return templates.TemplateResponse(
        request=request, name="company/levy.html", context={
            "request": request, "page_title": "장애인 고용부담금",
            "user_name": user["user_name"], "user_role": "company",
            "company": company, "levy": result,
        }
    )


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


@router.get("/jobs/{job_id}/applicants", response_class=HTMLResponse)
async def applicants_list(request: Request, job_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        job = conn.execute(
            "SELECT * FROM job_postings WHERE id=? AND company_id=?",
            (job_id, company["id"]),
        ).fetchone()
        if job is None:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
        applicants = conn.execute(
            """SELECT c.id, c.status, c.source, c.created_at,
                      u.name AS seeker_name
               FROM candidacies c
               JOIN users u ON c.seeker_user_id=u.id
               WHERE c.job_id=?
                 AND (c.source='direct' OR c.match_stage='submitted')
               ORDER BY c.created_at DESC""",
            (job_id,),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/applicants.html", context={
            "request": request, "page_title": f"지원자 목록 - {job['title']}",
            "user_name": user["user_name"], "user_role": "company",
            "job": job,
            "applicants": applicants,
            "status_labels": STATUS_LABELS,
        }
    )


@router.get("/jobs/{job_id}/applicants/{candidacy_id}", response_class=HTMLResponse)
async def applicant_detail(request: Request, job_id: int, candidacy_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        job = conn.execute(
            "SELECT * FROM job_postings WHERE id=? AND company_id=?",
            (job_id, company["id"]),
        ).fetchone()
        if job is None:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
        cand = conn.execute(
            """SELECT c.*, u.name AS seeker_name
               FROM candidacies c
               JOIN users u ON c.seeker_user_id=u.id
               WHERE c.id=? AND c.job_id=?
                 AND (c.source='direct' OR c.match_stage='submitted')""",
            (candidacy_id, job_id),
        ).fetchone()
        if cand is None:
            raise HTTPException(status_code=404, detail="지원자를 찾을 수 없습니다.")
        profile = conn.execute(
            """SELECT sp.*, dt.name AS disability_name,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM seeker_profiles sp
               LEFT JOIN disability_types dt ON sp.disability_type_id=dt.id
               LEFT JOIN regions r ON sp.region_id=r.id
               WHERE sp.user_id=?""",
            (cand["seeker_user_id"],),
        ).fetchone()
        history = conn.execute(
            """SELECT sh.*, u.name AS actor_name
               FROM status_history sh
               LEFT JOIN users u ON sh.actor_id=u.id
               WHERE sh.candidacy_id=?
               ORDER BY sh.created_at ASC""",
            (candidacy_id,),
        ).fetchall()
        conn.execute(
            "INSERT INTO access_log (viewer_id, seeker_user_id, purpose) VALUES (?,?,?)",
            (user["user_id"], cand["seeker_user_id"], "applicant_review"),
        )
        conn.commit()
        current_status = cand["status"]
        next_statuses = TRANSITIONS.get(current_status, []) if current_status not in TERMINAL else []
        interview = conn.execute(
            "SELECT * FROM interview_schedules WHERE candidacy_id=?", (candidacy_id,)
        ).fetchone()
        notes = conn.execute(
            """SELECT n.*, u.name AS author_name
               FROM applicant_notes n
               LEFT JOIN users u ON n.author_id=u.id
               WHERE n.candidacy_id=?
               ORDER BY n.created_at DESC""",
            (candidacy_id,),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/applicant_detail.html", context={
            "request": request, "page_title": f"지원자 상세 - {cand['seeker_name']}",
            "user_name": user["user_name"], "user_role": "company",
            "job": job,
            "cand": cand,
            "profile": profile,
            "history": history,
            "next_statuses": next_statuses,
            "status_labels": STATUS_LABELS,
            "interview": interview,
            "notes": notes,
        }
    )


@router.post("/jobs/{job_id}/applicants/{candidacy_id}/status")
async def applicant_status_change(
    request: Request,
    job_id: int,
    candidacy_id: int,
    status: str = Form(...),
    comment: str = Form(""),
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        job = conn.execute(
            "SELECT id FROM job_postings WHERE id=? AND company_id=?",
            (job_id, company["id"]),
        ).fetchone()
        if job:
            apply_transition(conn, candidacy_id, status, user["user_id"], comment)
    finally:
        conn.close()
    return RedirectResponse(url=f"/company/jobs/{job_id}/applicants", status_code=303)


@router.get("/talents", response_class=HTMLResponse)
async def talent_search(
    request: Request,
    q: Optional[str] = Query(None),
    disability_type: Optional[str] = Query(None),
    region_id: Optional[int] = Query(None),
    sido: Optional[str] = Query(None),
    work_pref: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT sp.*, u.name AS seeker_name, dt.name AS disability_name, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM seeker_profiles sp "
            "JOIN users u ON sp.user_id=u.id "
            "LEFT JOIN disability_types dt ON sp.disability_type_id=dt.id "
            "LEFT JOIN regions r ON sp.region_id=r.id "
            "WHERE sp.consent_sensitive=1"
        )
        params = []
        if q:
            sql += " AND (u.name LIKE ? OR sp.desired_job LIKE ? OR sp.experience_summary LIKE ?)"
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        if disability_type:
            sql += " AND dt.name=?"
            params.append(disability_type)
        if region_id:
            sql += " AND sp.region_id=?"
            params.append(region_id)
        elif sido:
            sql += " AND r.sido=?"
            params.append(sido)
        if work_pref:
            sql += " AND sp.work_pref=?"
            params.append(work_pref)

        sql += " ORDER BY sp.updated_at DESC"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        pagination = page_info(total, page)
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        talents = conn.execute(sql, params).fetchall()

        company = conn.execute(
            "SELECT id FROM companies WHERE user_id=?", (user["user_id"],)
        ).fetchone()
        offered_ids = set()
        if company:
            rows = conn.execute(
                "SELECT seeker_user_id FROM talent_offers WHERE company_user_id=?",
                (user["user_id"],),
            ).fetchall()
            offered_ids = {r["seeker_user_id"] for r in rows}

        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
    finally:
        conn.close()

    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if sido: qs_parts.append(f"sido={sido}")
    if disability_type: qs_parts.append(f"disability_type={disability_type}")
    if work_pref: qs_parts.append(f"work_pref={work_pref}")
    base_qs = "&".join(qs_parts)

    return templates.TemplateResponse(
        request=request,
        name="company/talents.html",
        context={
            "request": request, "page_title": "인재 검색",
            "user_name": user["user_name"], "user_role": "company",
            "talents": talents, "offered_ids": offered_ids,
            "disability_types": disability_types,
            "q": q or "", "selected_sido": sido or "",
            "selected_disability": disability_type or "",
            "selected_work_pref": work_pref or "",
            "pagination": pagination, "base_qs": base_qs,
        },
    )


@router.get("/talent/{seeker_user_id}", response_class=HTMLResponse)
async def talent_detail(request: Request, seeker_user_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        profile = conn.execute(
            "SELECT sp.*, u.name AS seeker_name, dt.name AS disability_name, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM seeker_profiles sp "
            "JOIN users u ON sp.user_id=u.id "
            "LEFT JOIN disability_types dt ON sp.disability_type_id=dt.id "
            "LEFT JOIN regions r ON sp.region_id=r.id "
            "WHERE sp.user_id=?",
            (seeker_user_id,),
        ).fetchone()
        if not profile:
            return RedirectResponse(url="/company/talents", status_code=303)

        certs = conn.execute(
            "SELECT * FROM seeker_certifications WHERE user_id=? ORDER BY cert_date DESC",
            (seeker_user_id,),
        ).fetchall()

        offered = bool(conn.execute(
            "SELECT 1 FROM talent_offers WHERE seeker_user_id=? AND company_user_id=?",
            (seeker_user_id, user["user_id"]),
        ).fetchone())

        company = conn.execute(
            "SELECT company_name FROM companies WHERE user_id=?", (user["user_id"],)
        ).fetchone()
    finally:
        conn.close()

    comm_pref = []
    assistive = []
    accommodation = []
    try:
        comm_pref = json.loads(profile["communication_pref"] or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        assistive = json.loads(profile["assistive_tech"] or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        accommodation = json.loads(profile["accommodation_needs"] or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    return templates.TemplateResponse(
        request=request,
        name="company/talent_detail.html",
        context={
            "request": request, "page_title": "인재 프로필",
            "user_name": user["user_name"], "user_role": "company",
            "profile": profile, "certs": certs,
            "offered": offered,
            "company_name": company["company_name"] if company else "",
            "comm_pref": comm_pref, "assistive": assistive,
            "accommodation": accommodation,
        },
    )


@api_router.post("/api/talent_offer/{seeker_user_id}")
async def send_talent_offer(
    request: Request,
    seeker_user_id: int,
    title: str = Form(...),
    message: str = Form(...),
    contact: str = Form(""),
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute(
            "SELECT company_name FROM companies WHERE user_id=?", (user["user_id"],)
        ).fetchone()
        company_name = company["company_name"] if company else ""
        conn.execute(
            "INSERT INTO talent_offers (seeker_user_id, company_user_id, company_name, title, message, contact) "
            "VALUES (?,?,?,?,?,?)",
            (seeker_user_id, user["user_id"], company_name, title, message, contact),
        )
        create_notification(
            conn, seeker_user_id,
            f"{company_name}에서 입사 제안을 보냈습니다",
            "/proposals",
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/company/talent/{seeker_user_id}?offered=1", status_code=303)



@router.post("/jobs/{job_id}/applicants/{candidacy_id}/interview")
async def save_interview(
    request: Request,
    job_id: int,
    candidacy_id: int,
    interview_date: str = Form(...),
    interview_time: str = Form("10:00"),
    interview_type: str = Form("onsite"),
    location: str = Form(""),
    memo: str = Form(""),
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT id FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        job = conn.execute(
            "SELECT id FROM job_postings WHERE id=? AND company_id=?",
            (job_id, company["id"]),
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404)
        existing = conn.execute(
            "SELECT id FROM interview_schedules WHERE candidacy_id=?", (candidacy_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE interview_schedules SET interview_date=?, interview_time=?,
                   interview_type=?, location=?, memo=?, updated_at=datetime('now','localtime')
                   WHERE candidacy_id=?""",
                (interview_date, interview_time, interview_type, location, memo, candidacy_id),
            )
        else:
            conn.execute(
                """INSERT INTO interview_schedules
                   (candidacy_id, interview_date, interview_time, interview_type, location, memo)
                   VALUES (?,?,?,?,?,?)""",
                (candidacy_id, interview_date, interview_time, interview_type, location, memo),
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(
        url=f"/company/jobs/{job_id}/applicants/{candidacy_id}", status_code=303
    )



@router.post("/jobs/{job_id}/applicants/{candidacy_id}/note")
async def add_note(
    request: Request,
    job_id: int,
    candidacy_id: int,
    content: str = Form(...),
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT id FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        conn.execute(
            "INSERT INTO applicant_notes (candidacy_id, author_id, content) VALUES (?,?,?)",
            (candidacy_id, user["user_id"], content),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(
        url=f"/company/jobs/{job_id}/applicants/{candidacy_id}", status_code=303
    )



ATTENDANCE_STATUS_LABELS = {
    "normal": "정상",
    "late": "지각",
    "early_leave": "조퇴",
    "absent": "결근",
    "vacation": "휴가",
    "half_day": "반차",
}


def _get_hired_employees(conn, company_id):
    return conn.execute(
        """SELECT DISTINCT u.id AS user_id, u.name AS user_name
           FROM placements p
           JOIN users u ON p.seeker_user_id=u.id
           WHERE p.company_id=?
           ORDER BY u.name""",
        (company_id,),
    ).fetchall()


@router.get("/attendance", response_class=HTMLResponse)
async def attendance_daily(request: Request, date: str = ""):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)

        work_date = date if date else datetime.now().strftime("%Y-%m-%d")
        employees = _get_hired_employees(conn, company["id"])

        records = {}
        rows = conn.execute(
            "SELECT * FROM attendance WHERE company_id=? AND work_date=?",
            (company["id"], work_date),
        ).fetchall()
        for r in rows:
            records[r["employee_user_id"]] = r
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="company/attendance.html", context={
            "request": request, "page_title": "근태관리",
            "user_name": user["user_name"], "user_role": "company",
            "work_date": work_date,
            "employees": employees,
            "records": records,
            "status_labels": ATTENDANCE_STATUS_LABELS,
        }
    )


@router.post("/attendance")
async def attendance_save(request: Request):
    user = require_role(request, "company")
    form = await request.form()
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT id FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        work_date = form.get("work_date", "")
        employee_ids = form.getlist("employee_user_id")
        for eid in employee_ids:
            eid_int = int(eid)
            check_in = form.get(f"check_in_{eid}", "") or None
            check_out = form.get(f"check_out_{eid}", "") or None
            status = form.get(f"status_{eid}", "normal")
            memo = form.get(f"memo_{eid}", "")
            conn.execute(
                """INSERT INTO attendance (company_id, employee_user_id, work_date, check_in, check_out, status, memo)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(company_id, employee_user_id, work_date)
                   DO UPDATE SET check_in=excluded.check_in, check_out=excluded.check_out,
                                 status=excluded.status, memo=excluded.memo,
                                 updated_at=datetime('now','localtime')""",
                (company["id"], eid_int, work_date, check_in, check_out, status, memo),
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/company/attendance?date={work_date}", status_code=303)


@router.get("/attendance/monthly", response_class=HTMLResponse)
async def attendance_monthly(
    request: Request,
    year: int = 0,
    month: int = 0,
):
    user = require_role(request, "company")
    today = date.today()
    if year == 0:
        year = today.year
    if month == 0:
        month = today.month

    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)

        employees = _get_hired_employees(conn, company["id"])
        days_in_month = calendar.monthrange(year, month)[1]

        date_from = f"{year}-{month:02d}-01"
        date_to = f"{year}-{month:02d}-{days_in_month:02d}"
        rows = conn.execute(
            "SELECT * FROM attendance WHERE company_id=? AND work_date BETWEEN ? AND ?",
            (company["id"], date_from, date_to),
        ).fetchall()

        grid = {}
        for r in rows:
            grid[(r["employee_user_id"], r["work_date"])] = r["status"]

        summaries = {}
        for emp in employees:
            uid = emp["user_id"]
            s = {"work": 0, "late": 0, "absent": 0, "vacation": 0, "half_day": 0, "early_leave": 0}
            for day in range(1, days_in_month + 1):
                d = f"{year}-{month:02d}-{day:02d}"
                st = grid.get((uid, d), "")
                if st == "normal":
                    s["work"] += 1
                elif st in s:
                    s[st] += 1
            summaries[uid] = s
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="company/attendance_monthly.html", context={
            "request": request, "page_title": "월간 근태 현황",
            "user_name": user["user_name"], "user_role": "company",
            "year": year, "month": month,
            "days_in_month": days_in_month,
            "employees": employees,
            "grid": grid,
            "summaries": summaries,
            "status_labels": ATTENDANCE_STATUS_LABELS,
        }
    )
