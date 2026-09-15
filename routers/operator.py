from core.security import hash_password, MIN_PASSWORD_LENGTH
from core.logger import log
import json
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import STATUS_LABELS, MATCH_STAGE_LABELS, EMPLOYMENT_TYPES, COMPANY_SIZES, INDUSTRY_TYPES
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification
from core.matching import build_capability_profile, calc_category_fit


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
            "user_name": user["name"], "user_role": "operator",
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
            (user["id"], user_id, "operator_view"),
        )
        create_notification(
            conn, user_id,
            "운영자가 프로필을 열람했습니다.",
            "/profile/views",
        )
        conn.commit()
        recent_consultations = conn.execute(
            "SELECT c.*, u.name AS operator_name "
            "FROM consultations c JOIN users u ON c.operator_user_id = u.id "
            "WHERE c.seeker_user_id=? ORDER BY c.created_at DESC LIMIT 3",
            (user_id,),
        ).fetchall()
        consult_count = conn.execute(
            "SELECT COUNT(*) FROM consultations WHERE seeker_user_id=?", (user_id,)
        ).fetchone()[0]
        managers = conn.execute("SELECT id, name FROM users WHERE role='manager' ORDER BY name").fetchall()
        current_assignment = conn.execute(
            "SELECT manager_user_id FROM manager_assignments WHERE seeker_user_id=?", (user_id,)
        ).fetchone()
        support_items = conn.execute(
            """SELECT si.name, si.description, sc.name AS cat_name
               FROM seeker_support_items ssi
               JOIN support_items si ON ssi.support_item_id = si.id
               JOIN support_categories sc ON si.category_id = sc.id
               WHERE ssi.user_id = ?
               ORDER BY sc.sort_order, si.sort_order""",
            (user_id,),
        ).fetchall()
        cap_profile = build_capability_profile(conn, user_id)
        cap_non_default = {k: v for k, v in cap_profile.items() if v != "ok"}
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/seeker_detail.html", context={
            "request": request, "page_title": f"구직자 상세 - {seeker['name']}",
            "user_name": user["name"], "user_role": "operator",
            "seeker": seeker,
            "profile": profile,
            "certifications": certifications,
            "communication_pref_display": _parse_json_list(profile["communication_pref"]) if profile else '-',
            "assistive_tech_display": _parse_json_list(profile["assistive_tech"]) if profile else '-',
            "accommodation_needs_display": _parse_json_list(profile["accommodation_needs"]) if profile else '-',
            "recent_consultations": recent_consultations,
            "consult_count": consult_count,
            "managers": managers,
            "current_assignment": current_assignment,
            "support_items": support_items,
            "cap_non_default": cap_non_default,
        }
    )


@router.post("/seekers/{seeker_id}/assign-manager")
async def op_assign_manager(
    request: Request,
    seeker_id: int,
    manager_id: int = Form(...),
):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        mgr = conn.execute("SELECT id FROM users WHERE id=? AND role='manager'", (manager_id,)).fetchone()
        if not mgr:
            raise HTTPException(status_code=400, detail="유효하지 않은 매니저입니다.")
        conn.execute(
            "INSERT OR REPLACE INTO manager_assignments (manager_user_id, seeker_user_id, assigned_by) VALUES (?,?,?)",
            (manager_id, seeker_id, request.session.get("id")),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/seekers/{seeker_id}", status_code=303)


@router.get("/companies", response_class=HTMLResponse)
async def op_companies(
    request: Request,
    q: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    company_size: Optional[str] = Query(None),
    sido: Optional[str] = Query(None),
    hiring_experience: Optional[str] = Query(None),
    approval: Optional[str] = Query(None),
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
        if approval in ("pending", "approved", "rejected"):
            sql += " AND c.approval_status=?"
            params.append(approval)
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
    if approval: qs_parts.append(f"approval={approval}")
    return templates.TemplateResponse(
        request=request, name="op/companies.html", context={
            "request": request, "page_title": "기업 목록",
            "user_name": user["name"], "user_role": "operator",
            "companies": companies,
            "company_sizes": COMPANY_SIZES,
            "industry_types": INDUSTRY_TYPES,
            "q": q or "",
            "selected_industry": industry or "",
            "selected_size": company_size or "",
            "selected_sido": sido or "",
            "selected_hiring": hiring_experience or "",
            "selected_approval": approval or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/companies/{company_id}", response_class=HTMLResponse)
async def op_company_detail(request: Request, company_id: int):
    user = require_role(request, "operator")
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
        if company is None:
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
        request=request, name="op/company_detail.html", context={
            "request": request, "page_title": f"기업 상세 - {company['company_name']}",
            "user_name": user["name"], "user_role": "operator",
            "company": company,
            "active_jobs": active_jobs,
            "placed_count": placed_count,
            "reviews": reviews,
            "avg_rating": avg_rating,
        }
    )


@router.post("/companies/{company_id}/approve")
async def op_company_approve(request: Request, company_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute("UPDATE companies SET approval_status='approved', rejection_reason='' WHERE id=?", (company_id,))
        company = conn.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)).fetchone()
        if company:
            create_notification(conn, company["user_id"], "사업자 인증이 승인되었습니다.", "/company/profile")
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/companies/{company_id}", status_code=303)


@router.post("/companies/{company_id}/reject")
async def op_company_reject(request: Request, company_id: int):
    require_role(request, "operator")
    form = await request.form()
    reason = form.get("rejection_reason", "")
    conn = get_sqlite()
    try:
        conn.execute("UPDATE companies SET approval_status='rejected', rejection_reason=? WHERE id=?", (reason, company_id))
        company = conn.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)).fetchone()
        if company:
            create_notification(conn, company["user_id"], "사업자 인증이 반려되었습니다. 사유를 확인해 주세요.", "/company/profile")
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/companies/{company_id}", status_code=303)


@router.post("/companies/{company_id}/reviews/{review_id}/delete")
async def op_delete_review(request: Request, company_id: int, review_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute(
            "DELETE FROM company_reviews WHERE id=? AND company_id=?",
            (review_id, company_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/companies/{company_id}", status_code=303)


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
            "r.sido AS region_sido, r.sigungu AS region_sigungu, "
            "(SELECT COUNT(*) FROM candidacies ca WHERE ca.job_id=jp.id) AS applicant_count "
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
            "user_name": user["name"], "user_role": "operator",
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
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM candidacies WHERE job_id=? GROUP BY status",
            (job_id,),
        ).fetchall()
    finally:
        conn.close()
    if not job:
        return RedirectResponse(url="/op/jobs", status_code=303)
    _labels = {
        "pending": "접수", "reviewing": "검토중", "shortlisted": "서류합격",
        "interview": "면접", "offer": "제의", "hired": "채용",
        "rejected": "불합격", "withdrawn": "지원취소",
    }
    status_breakdown = [(_labels.get(r["status"], r["status"]), r["cnt"]) for r in status_rows]
    total_applicants = sum(r["cnt"] for r in status_rows)
    accommodations = json.loads(job["accommodations_provided"]) if job["accommodations_provided"] else []
    return templates.TemplateResponse(
        request=request, name="op/job_detail.html", context={
            "request": request, "page_title": job["title"],
            "user_name": user["name"], "user_role": "operator",
            "job": job,
            "accommodations": accommodations,
            "status_breakdown": status_breakdown,
            "total_applicants": total_applicants,
        }
    )



@router.post("/jobs/{job_id}/approve")
async def op_job_approve(request: Request, job_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE job_postings SET status='open', rejection_reason='' WHERE id=?",
            (job_id,),
        )
        job = conn.execute(
            "SELECT jp.title, c.user_id FROM job_postings jp JOIN companies c ON jp.company_id=c.id WHERE jp.id=?",
            (job_id,),
        ).fetchone()
        if job:
            create_notification(
                conn, job["user_id"],
                f"[{job['title']}] 공고가 승인되어 게시되었습니다.",
                "/company/jobs",
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/reject")
async def op_job_reject(request: Request, job_id: int):
    require_role(request, "operator")
    form = await request.form()
    reason = form.get("rejection_reason", "")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE job_postings SET status='rejected', rejection_reason=? WHERE id=?",
            (reason, job_id),
        )
        job = conn.execute(
            "SELECT jp.title, c.user_id FROM job_postings jp JOIN companies c ON jp.company_id=c.id WHERE jp.id=?",
            (job_id,),
        ).fetchone()
        if job:
            create_notification(
                conn, job["user_id"],
                f"[{job['title']}] 공고가 반려되었습니다. 사유를 확인해 주세요.",
                "/company/jobs",
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/jobs/{job_id}", status_code=303)


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
                    "user_name": user["name"], "user_role": "operator",
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

        job_category = None
        if job and job["category_id"]:
            job_category = conn.execute(
                "SELECT * FROM job_categories WHERE id=?", (job["category_id"],)
            ).fetchone()

        compatibility = {}
        for c in candidates:
            seeker_needs = json.loads(c["accommodation_needs"]) if c["accommodation_needs"] else []
            cap_profile = build_capability_profile(conn, c["id"])
            fit = calc_category_fit(cap_profile, job_category) if job_category else 3.0
            if fit >= 2:
                fit_label = "적합"
            elif fit >= 1:
                fit_label = "조건부"
            else:
                fit_label = ""
            compatibility[c["id"]] = {
                "region": c["region_sido"] == job_region_sido if job_region_sido and c["region_sido"] else False,
                "hours": (c["daily_work_hours"] or 8) >= job_min_hours,
                "accommodation": len(set(seeker_needs) & set(job_accommodations)) if seeker_needs and job_accommodations else 0,
                "accommodation_total": len(seeker_needs) if seeker_needs else 0,
                "fit_score": fit,
                "fit_label": fit_label,
            }
        # fit_score 내림차순 정렬
        candidates = sorted(candidates, key=lambda c: compatibility[c["id"]]["fit_score"], reverse=True)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="op/matching.html", context={
            "request": request, "page_title": "매칭 - 후보자 선택",
            "user_name": user["name"], "user_role": "operator",
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
            (cur.lastrowid, user["id"]),
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
        sql = """SELECT c.id, c.seeker_user_id, c.status, c.source, c.match_stage, c.created_at,
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
            "user_name": user["name"], "user_role": "operator",
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
                (candidacy_id, cand["status"], cand["status"], user["id"]),
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


@router.get("/consultations", response_class=HTMLResponse)
async def op_consultations(request: Request, seeker_id: int = Query(...)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        seeker = conn.execute(
            "SELECT * FROM users WHERE id=? AND role='seeker'", (seeker_id,)
        ).fetchone()
        if not seeker:
            raise HTTPException(status_code=404)
        rows = conn.execute(
            "SELECT c.*, u.name AS operator_name "
            "FROM consultations c "
            "JOIN users u ON c.operator_user_id = u.id "
            "WHERE c.seeker_user_id=? ORDER BY c.created_at DESC",
            (seeker_id,),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/consultation_list.html", context={
            "request": request, "page_title": f"{seeker['name']} - 상담 기록",
            "user_name": user["name"], "user_role": "operator",
            "seeker": seeker,
            "consultations": rows,
        }
    )


@router.get("/consultations/new", response_class=HTMLResponse)
async def op_consultation_new(request: Request, seeker_id: int = Query(...)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        seeker = conn.execute(
            "SELECT * FROM users WHERE id=? AND role='seeker'", (seeker_id,)
        ).fetchone()
    finally:
        conn.close()
    if not seeker:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request=request, name="op/consultation_form.html", context={
            "request": request, "page_title": "새 상담 기록",
            "user_name": user["name"], "user_role": "operator",
            "seeker": seeker,
            "consultation": None,
        }
    )


@router.post("/consultations")
async def op_consultation_create(
    request: Request,
    seeker_id: int = Form(...),
    physical_note: str = Form(""),
    sensory_note: str = Form(""),
    cognitive_note: str = Form(""),
    communication_note: str = Form(""),
    work_capacity_note: str = Form(""),
    environment_note: str = Form(""),
    summary: str = Form(""),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO consultations "
            "(seeker_user_id, operator_user_id, physical_note, sensory_note, "
            "cognitive_note, communication_note, work_capacity_note, environment_note, summary) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (seeker_id, user["id"], physical_note.strip(), sensory_note.strip(),
             cognitive_note.strip(), communication_note.strip(),
             work_capacity_note.strip(), environment_note.strip(), summary.strip()),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/consultations?seeker_id={seeker_id}", status_code=303)


@router.get("/consultations/{consultation_id}/edit", response_class=HTMLResponse)
async def op_consultation_edit(request: Request, consultation_id: int):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT * FROM consultations WHERE id=?", (consultation_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404)
        seeker = conn.execute(
            "SELECT * FROM users WHERE id=?", (row["seeker_user_id"],)
        ).fetchone()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/consultation_form.html", context={
            "request": request, "page_title": "상담 기록 수정",
            "user_name": user["name"], "user_role": "operator",
            "seeker": seeker,
            "consultation": row,
        }
    )


@router.post("/consultations/{consultation_id}")
async def op_consultation_update(
    request: Request,
    consultation_id: int,
    seeker_id: int = Form(...),
    physical_note: str = Form(""),
    sensory_note: str = Form(""),
    cognitive_note: str = Form(""),
    communication_note: str = Form(""),
    work_capacity_note: str = Form(""),
    environment_note: str = Form(""),
    summary: str = Form(""),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE consultations SET "
            "physical_note=?, sensory_note=?, cognitive_note=?, "
            "communication_note=?, work_capacity_note=?, environment_note=?, "
            "summary=?, updated_at=datetime('now','localtime') WHERE id=?",
            (physical_note.strip(), sensory_note.strip(), cognitive_note.strip(),
             communication_note.strip(), work_capacity_note.strip(),
             environment_note.strip(), summary.strip(), consultation_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/consultations?seeker_id={seeker_id}", status_code=303)


@router.get("/placements", response_class=HTMLResponse)
async def op_placements(request: Request, company_id: Optional[int] = Query(None)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = """
            SELECT p.*, u.name AS seeker_name, jp.title AS job_title,
                   c.company_name, sp.disability_type_id, dt.name AS disability_name, sp.severity
            FROM placements p
            JOIN users u ON p.seeker_user_id=u.id
            JOIN job_postings jp ON p.job_id=jp.id
            JOIN companies c ON p.company_id=c.id
            LEFT JOIN seeker_profiles sp ON p.seeker_user_id=sp.user_id
            LEFT JOIN disability_types dt ON sp.disability_type_id=dt.id
        """
        params = []
        if company_id:
            sql += " WHERE p.company_id=?"
            params.append(company_id)
        sql += " ORDER BY p.created_at DESC"
        placements = conn.execute(sql, params).fetchall()

        total = len(placements)

        avg_tenure = 0
        if total:
            if company_id:
                tenure_sql = "SELECT AVG(julianday('now','localtime') - julianday(start_date)) FROM placements WHERE start_date != '' AND (end_date IS NULL OR end_date='') AND company_id=?"
                row = conn.execute(tenure_sql, (company_id,)).fetchone()
            else:
                tenure_sql = "SELECT AVG(julianday('now','localtime') - julianday(start_date)) FROM placements WHERE start_date != '' AND (end_date IS NULL OR end_date='')"
                row = conn.execute(tenure_sql).fetchone()
            avg_tenure = round(row[0]) if row[0] else 0

        companies = conn.execute(
            "SELECT DISTINCT c.id, c.company_name FROM companies c JOIN placements p ON c.id=p.company_id ORDER BY c.company_name"
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/placements.html", context={
            "request": request, "page_title": "배치 관리",
            "user_name": user["name"], "user_role": user["role"],
            "placements": placements,
            "total": total,
            "avg_tenure": avg_tenure,
            "companies": companies,
            "selected_company": company_id,
        }
    )


@router.delete("/consultations/{consultation_id}")
async def op_consultation_delete(request: Request, consultation_id: int):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT seeker_user_id FROM consultations WHERE id=?", (consultation_id,)).fetchone()
        seeker_id = row["seeker_user_id"] if row else None
        conn.execute("DELETE FROM consultations WHERE id=?", (consultation_id,))
        conn.commit()
    finally:
        conn.close()
    url = f"/op/consultations?seeker_id={seeker_id}" if seeker_id else "/op/seekers"
    return JSONResponse({"redirect": url})



@router.get("/access-log", response_class=HTMLResponse)
async def op_access_log(request: Request, page: int = Query(1)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        total = conn.execute("SELECT COUNT(*) FROM access_log").fetchone()[0]
        pagination = page_info(total, page)
        logs = conn.execute(
            """SELECT al.*,
                      v.name AS viewer_name, v.role AS viewer_role,
                      s.name AS seeker_name
               FROM access_log al
               JOIN users v ON al.viewer_id = v.id
               JOIN users s ON al.seeker_user_id = s.id
               ORDER BY al.created_at DESC
               LIMIT ? OFFSET ?""",
            (pagination["per_page"], (pagination["page"] - 1) * pagination["per_page"]),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/access_log.html", context={
            "request": request, "page_title": "열람 기록",
            "user_name": user["name"], "user_role": "operator",
            "logs": logs,
            "pagination": pagination,
            "base_qs": "",
        }
    )
