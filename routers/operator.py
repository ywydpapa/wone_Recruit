from core.security import hash_password, MIN_PASSWORD_LENGTH
from core.logger import log
import json
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import STATUS_LABELS, MATCH_STAGE_LABELS, EMPLOYMENT_TYPES, COMPANY_SIZES, INDUSTRY_TYPES
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification


def _parse_json_list(val):
    if not val or val == '[]':
        return '-'
    try:
        items = json.loads(val)
        return ', '.join(items) if items else '-'
    except (json.JSONDecodeError, TypeError):
        return val

router = APIRouter(prefix="/op")



@router.get("/seekers", response_class=HTMLResponse)
async def op_seekers(
    request: Request,
    q: Optional[str] = Query(None),
    disability_type_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    sido: Optional[str] = Query(None),
    consent: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
        sql = (
            "SELECT u.id, u.name, u.username, "
            "sp.disability_type_id, dt.name AS disability_name, "
            "sp.severity, sp.consent_sensitive, "
            "sp.mobility_type, sp.daily_work_hours, sp.work_pref, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM users u "
            "LEFT JOIN seeker_profiles sp ON u.id = sp.user_id "
            "LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id "
            "LEFT JOIN regions r ON sp.region_id = r.id "
            "WHERE u.role = 'seeker'"
        )
        params = []
        if q:
            sql += " AND (u.name LIKE ? OR u.username LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if disability_type_id:
            sql += " AND sp.disability_type_id=?"
            params.append(disability_type_id)
        if severity:
            sql += " AND sp.severity=?"
            params.append(severity)
        if sido:
            sql += " AND r.sido=?"
            params.append(sido)
        if consent == "1":
            sql += " AND sp.consent_sensitive=1"
        elif consent == "0":
            sql += " AND (sp.consent_sensitive=0 OR sp.consent_sensitive IS NULL)"
        sql += " ORDER BY u.id"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        seekers = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if disability_type_id: qs_parts.append(f"disability_type_id={disability_type_id}")
    if severity: qs_parts.append(f"severity={severity}")
    if sido: qs_parts.append(f"sido={sido}")
    if consent: qs_parts.append(f"consent={consent}")
    return templates.TemplateResponse(
        request=request, name="op/seekers.html", context={
            "request": request, "page_title": "구직자 목록",
            "user_name": user["user_name"], "user_role": "operator",
            "seekers": seekers,
            "disability_types": disability_types,
            "q": q or "",
            "selected_disability": disability_type_id or "",
            "selected_severity": severity or "",
            "selected_sido": sido or "",
            "selected_consent": consent or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/seekers/{user_id}", response_class=HTMLResponse)
async def op_seeker_detail(request: Request, user_id: int):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        seeker = conn.execute(
            "SELECT * FROM users WHERE id=? AND role='seeker'", (user_id,)
        ).fetchone()
        if seeker is None:
            raise HTTPException(status_code=404, detail="구직자를 찾을 수 없습니다.")
        profile = conn.execute(
            """SELECT sp.*, dt.name AS disability_name,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM seeker_profiles sp
               LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id
               LEFT JOIN regions r ON sp.region_id = r.id
               WHERE sp.user_id = ?""",
            (user_id,),
        ).fetchone()
        certifications = conn.execute(
            "SELECT * FROM seeker_certifications WHERE user_id=? ORDER BY id",
            (user_id,),
        ).fetchall()
        conn.execute(
            "INSERT INTO access_log (viewer_id, seeker_user_id, purpose) VALUES (?,?,?)",
            (user["user_id"], user_id, "운영자 열람"),
        )
        conn.commit()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/seeker_detail.html", context={
            "request": request, "page_title": f"구직자 상세 - {seeker['name']}",
            "user_name": user["user_name"], "user_role": "operator",
            "seeker": seeker,
            "profile": profile,
            "certifications": certifications,
            "communication_pref_display": _parse_json_list(profile["communication_pref"]) if profile else '-',
            "assistive_tech_display": _parse_json_list(profile["assistive_tech"]) if profile else '-',
            "accommodation_needs_display": _parse_json_list(profile["accommodation_needs"]) if profile else '-',
        }
    )


@router.get("/companies", response_class=HTMLResponse)
async def op_companies(
    request: Request,
    q: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    company_size: Optional[str] = Query(None),
    sido: Optional[str] = Query(None),
    hiring_experience: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT c.*, u.name AS user_name_val, u.username, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM companies c "
            "JOIN users u ON c.user_id = u.id "
            "LEFT JOIN regions r ON c.region_id = r.id "
            "WHERE 1=1"
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
        if hiring_experience == "1":
            sql += " AND c.hiring_experience=1"
        elif hiring_experience == "0":
            sql += " AND (c.hiring_experience=0 OR c.hiring_experience IS NULL)"
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
    if hiring_experience: qs_parts.append(f"hiring_experience={hiring_experience}")
    return templates.TemplateResponse(
        request=request, name="op/companies.html", context={
            "request": request, "page_title": "기업 목록",
            "user_name": user["user_name"], "user_role": "operator",
            "companies": companies,
            "company_sizes": COMPANY_SIZES,
            "industry_types": INDUSTRY_TYPES,
            "q": q or "",
            "selected_industry": industry or "",
            "selected_size": company_size or "",
            "selected_sido": sido or "",
            "selected_hiring": hiring_experience or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/jobs", response_class=HTMLResponse)
async def op_jobs(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sido: Optional[str] = Query(None),
    employment_type: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT jp.*, c.company_name, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM job_postings jp "
            "JOIN companies c ON jp.company_id = c.id "
            "LEFT JOIN regions r ON jp.region_id = r.id "
            "WHERE 1=1"
        )
        params = []
        if q:
            sql += " AND (jp.title LIKE ? OR jp.description LIKE ? OR c.company_name LIKE ?)"
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
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
        request=request, name="op/jobs.html", context={
            "request": request, "page_title": "전체 공고",
            "user_name": user["user_name"], "user_role": "operator",
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
async def op_job_detail(request: Request, job_id: int):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        job = conn.execute(
            """SELECT jp.*, c.company_name, jc.minor_name_ko AS category_name,
                      jc.fit_physical_lower, jc.fit_physical_upper,
                      jc.fit_hearing, jc.fit_visual_low,
                      jc.fit_intellectual, jc.fit_autism,
                      jc.fit_mental, jc.fit_internal_organ,
                      jc.fit_brain_lesion, jc.fit_notes,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM job_postings jp
               JOIN companies c ON jp.company_id = c.id
               LEFT JOIN job_categories jc ON jp.category_id = jc.id
               LEFT JOIN regions r ON jp.region_id = r.id
               WHERE jp.id = ?""",
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    if not job:
        return RedirectResponse(url="/op/jobs", status_code=303)
    return templates.TemplateResponse(
        request=request, name="op/job_detail.html", context={
            "request": request, "page_title": job["title"],
            "user_name": user["user_name"], "user_role": "operator",
            "job": job,
        }
    )



@router.get("/matching", response_class=HTMLResponse)
async def op_matching(request: Request, job_id: int = None):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        if job_id is None:
            open_jobs = conn.execute(
                """SELECT jp.*, c.company_name,
                          r.sido AS region_sido, r.sigungu AS region_sigungu
                   FROM job_postings jp
                   JOIN companies c ON jp.company_id = c.id
                   LEFT JOIN regions r ON jp.region_id = r.id
                   WHERE jp.status = 'open'
                   ORDER BY jp.created_at DESC"""
            ).fetchall()
            return templates.TemplateResponse(
                request=request, name="op/matching.html", context={
                    "request": request, "page_title": "매칭 - 공고 선택",
                    "user_name": user["user_name"], "user_role": "operator",
                    "open_jobs": open_jobs,
                    "job": None,
                    "candidates": None,
                }
            )

        job = conn.execute(
            """SELECT jp.*, c.company_name,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM job_postings jp
               JOIN companies c ON jp.company_id = c.id
               LEFT JOIN regions r ON jp.region_id = r.id
               WHERE jp.id = ?""",
            (job_id,),
        ).fetchone()

        job_accommodations = json.loads(job["accommodations_provided"]) if job and job["accommodations_provided"] else []
        job_min_hours = job["min_work_hours"] if job else 8
        job_region_sido = job["region_sido"] if job else ""

        candidates = conn.execute(
            """SELECT u.id, u.name, sp.work_pref,
                      sp.severity, dt.name AS disability_name,
                      sp.desired_job,
                      sp.daily_work_hours, sp.accommodation_needs,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM users u
               JOIN seeker_profiles sp ON u.id = sp.user_id
               LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id
               LEFT JOIN regions r ON sp.region_id = r.id
               WHERE u.role = 'seeker'
                 AND sp.consent_sensitive = 1
                 AND u.id NOT IN (
                     SELECT seeker_user_id FROM candidacies WHERE job_id = ?
                 )
               ORDER BY u.id""",
            (job_id,),
        ).fetchall()

        compatibility = {}
        for c in candidates:
            seeker_needs = json.loads(c["accommodation_needs"]) if c["accommodation_needs"] else []
            compatibility[c["id"]] = {
                "region": c["region_sido"] == job_region_sido if job_region_sido and c["region_sido"] else False,
                "hours": (c["daily_work_hours"] or 8) >= job_min_hours,
                "accommodation": len(set(seeker_needs) & set(job_accommodations)) if seeker_needs and job_accommodations else 0,
                "accommodation_total": len(seeker_needs) if seeker_needs else 0,
            }
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="op/matching.html", context={
            "request": request, "page_title": "매칭 - 후보자 선택",
            "user_name": user["user_name"], "user_role": "operator",
            "open_jobs": None,
            "job": job,
            "job_id": job_id,
            "candidates": candidates,
            "compatibility": compatibility,
        }
    )


@router.post("/matching/propose")
async def op_propose(
    request: Request,
    job_id: int = Form(...),
    seeker_user_id: int = Form(...),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        cur = conn.execute(
            """INSERT INTO candidacies
               (job_id, seeker_user_id, source, status, match_stage)
               VALUES (?, ?, 'operator_matched', 'pending', 'proposed')""",
            (job_id, seeker_user_id),
        )
        conn.execute(
            """INSERT INTO status_history
               (candidacy_id, from_status, to_status, actor_id, comment)
               VALUES (?, '', 'pending', ?, '운영자 매칭 제안')""",
            (cur.lastrowid, user["user_id"]),
        )
        job = conn.execute("SELECT title FROM job_postings WHERE id=?", (job_id,)).fetchone()
        job_title = job["title"] if job else "공고"
        create_notification(conn, seeker_user_id, f"[{job_title}] 운영자가 매칭을 제안했습니다.", "/proposals")
        conn.commit()
    except Exception:
        log.exception("매칭 제안 실패: job_id=%s seeker=%s", job_id, seeker_user_id)
        conn.rollback()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/matching?job_id={job_id}", status_code=303)


@router.get("/candidacies", response_class=HTMLResponse)
async def op_candidacies(request: Request, page: int = Query(1)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = """SELECT c.id, c.status, c.source, c.match_stage, c.created_at,
                      jp.title AS job_title,
                      co.company_name,
                      u.name AS seeker_name
               FROM candidacies c
               JOIN job_postings jp ON c.job_id = jp.id
               JOIN companies co ON jp.company_id = co.id
               JOIN users u ON c.seeker_user_id = u.id
               ORDER BY c.created_at DESC"""
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})").fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        candidacies = conn.execute(sql).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/candidacies.html", context={
            "request": request, "page_title": "전체 지원 현황",
            "user_name": user["user_name"], "user_role": "operator",
            "candidacies": candidacies,
            "status_labels": STATUS_LABELS,
            "match_stage_labels": MATCH_STAGE_LABELS,
            "pagination": pagination, "base_qs": "",
        }
    )


@router.post("/matching/{candidacy_id}/submit")
async def op_submit(request: Request, candidacy_id: int):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        cand = conn.execute(
            "SELECT * FROM candidacies WHERE id=?", (candidacy_id,)
        ).fetchone()
        if cand and cand["match_stage"] == "seeker_confirmed":
            conn.execute(
                """UPDATE candidacies SET match_stage='submitted',
                   updated_at=datetime('now','localtime') WHERE id=?""",
                (candidacy_id,),
            )
            conn.execute(
                """INSERT INTO status_history
                   (candidacy_id, from_status, to_status, actor_id, comment)
                   VALUES (?, ?, ?, ?, '기업에 매칭 전달')""",
                (candidacy_id, cand["status"], cand["status"], user["user_id"]),
            )
            job = conn.execute(
                "SELECT jp.title, c.user_id as company_user_id "
                "FROM job_postings jp JOIN companies c ON jp.company_id=c.id WHERE jp.id=?",
                (cand["job_id"],),
            ).fetchone()
            if job:
                create_notification(
                    conn, job["company_user_id"],
                    f"[{job['title']}] 새로운 매칭 후보가 전달되었습니다.",
                    f"/company/jobs/{cand['job_id']}/applicants",
                )
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/op/candidacies", status_code=303)


@router.post("/users/{target_user_id}/reset-password")
async def op_reset_password(
    request: Request,
    target_user_id: int,
    new_password: str = Form(...),
):
    user = require_role(request, "operator")
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return RedirectResponse(url=f"/op/seekers/{target_user_id}", status_code=303)
    hashed = hash_password(new_password)
    conn = get_sqlite()
    try:
        target = conn.execute("SELECT id, role FROM users WHERE id=?", (target_user_id,)).fetchone()
        if target:
            conn.execute("UPDATE users SET password=? WHERE id=?", (hashed, target_user_id))
            conn.commit()
    finally:
        conn.close()
    referer = request.headers.get("referer", "/op/seekers")
    return RedirectResponse(url=referer, status_code=303)
