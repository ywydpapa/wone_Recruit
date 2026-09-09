import json
from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Query, Request
from core.logger import log
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.upload import save_upload
from core.constants import (
    EMPLOYMENT_TYPES, STATUS_LABELS,
    MOBILITY_TYPES, COMMUTE_OPTIONS,
    COMMUNICATION_OPTIONS, ASSISTIVE_TECH_OPTIONS,
    ACCOMMODATION_OPTIONS,
)
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification
from routers.resume import build_resume_snapshot

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
async def profile_form(request: Request, error: str = "", success: str = "", msg: str = ""):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        profile = conn.execute("SELECT * FROM seeker_profiles WHERE user_id=?", (user["id"],)).fetchone()
        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
        selected_sido = ""
        if profile and profile["region_id"]:
            region_row = conn.execute("SELECT sido FROM regions WHERE id=?", (profile["region_id"],)).fetchone()
            if region_row:
                selected_sido = region_row["sido"]
        communication_pref = json.loads(profile["communication_pref"]) if profile and profile["communication_pref"] else []
        assistive_tech = json.loads(profile["assistive_tech"]) if profile and profile["assistive_tech"] else []
        accommodation_needs = json.loads(profile["accommodation_needs"]) if profile and profile["accommodation_needs"] else []
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/profile_form.html", context={
            "request": request, "page_title": "내 프로필",
            "user_name": user["name"], "user_role": "seeker",
            "user": user,
            "profile": profile, "disability_types": disability_types,
            "selected_sido": selected_sido,
            "communication_pref": communication_pref,
            "assistive_tech": assistive_tech,
            "accommodation_needs": accommodation_needs,
            "mobility_types": MOBILITY_TYPES,
            "commute_options": COMMUTE_OPTIONS,
            "communication_options": COMMUNICATION_OPTIONS,
            "assistive_tech_options": ASSISTIVE_TECH_OPTIONS,
            "accommodation_options": ACCOMMODATION_OPTIONS,
            "error": error, "success": success, "msg": msg,
        }
    )


@router.post("/profile")
async def profile_save(request: Request):
    user = require_role(request, "seeker")
    form = await request.form()
    consent_sensitive = int(form.get("consent_sensitive", 0))
    if not consent_sensitive:
        return RedirectResponse(url="/profile?error=consent", status_code=303)

    disability_type_id = int(form.get("disability_type_id", 0))
    severity = form.get("severity", "경증")
    gender = form.get("gender", "")
    birth_year = int(form.get("birth_year") or 0) or None
    region_id = int(form.get("region_id") or 0) or None
    mobility_type = form.get("mobility_type", "")
    commute_max_minutes = int(form.get("commute_max_minutes") or 0) or None
    disability_visibility = form.get("disability_visibility", "manager_only")
    communication_pref = json.dumps(form.getlist("communication_pref"), ensure_ascii=False)
    assistive_tech = json.dumps(form.getlist("assistive_tech"), ensure_ascii=False)
    daily_work_hours = int(form.get("daily_work_hours") or 8)
    preferred_time = form.get("preferred_time", "풀타임")
    rest_frequency = form.get("rest_frequency", "불필요")
    accommodation_needs = json.dumps(form.getlist("accommodation_needs"), ensure_ascii=False)
    education_level = form.get("education_level", "")
    school_name = form.get("school_name", "")
    major = form.get("major", "")
    career_years = int(form.get("career_years") or 0)
    recent_company = form.get("recent_company", "")
    recent_job_title = form.get("recent_job_title", "")
    experience_summary = form.get("experience_summary", "")
    desired_job = form.get("desired_job", "")
    work_pref = form.get("work_pref", "무관")

    resume_file = form.get("resume")
    resume_path = ""
    if resume_file and hasattr(resume_file, "filename") and resume_file.filename:
        resume_path = await save_upload(
            resume_file, "profile_resumes", user["id"],
            ["application/pdf"], 10 * 1024 * 1024,
        )

    uid = user["id"]
    conn = get_sqlite()
    try:
        existing = conn.execute("SELECT id, resume_path FROM seeker_profiles WHERE user_id=?", (uid,)).fetchone()
        if not resume_path and existing:
            resume_path = existing["resume_path"] or ""
        if existing:
            conn.execute("""UPDATE seeker_profiles SET
                disability_type_id=?, severity=?, gender=?, birth_year=?, region_id=?,
                mobility_type=?, commute_max_minutes=?,
                communication_pref=?, assistive_tech=?,
                daily_work_hours=?, preferred_time=?, rest_frequency=?, accommodation_needs=?,
                education_level=?, school_name=?, major=?,
                career_years=?, recent_company=?, recent_job_title=?, experience_summary=?,
                desired_job=?, work_pref=?, resume_path=?,
                disability_visibility=?, consent_sensitive=?,
                consented_at=datetime('now','localtime'),
                updated_at=datetime('now','localtime')
                WHERE user_id=?""",
                (disability_type_id, severity, gender, birth_year, region_id,
                 mobility_type, commute_max_minutes,
                 communication_pref, assistive_tech,
                 daily_work_hours, preferred_time, rest_frequency, accommodation_needs,
                 education_level, school_name, major,
                 career_years, recent_company, recent_job_title, experience_summary,
                 desired_job, work_pref, resume_path,
                 disability_visibility, consent_sensitive, uid))
        else:
            conn.execute("""INSERT INTO seeker_profiles
                (user_id, disability_type_id, severity, gender, birth_year, region_id,
                 mobility_type, commute_max_minutes,
                 communication_pref, assistive_tech,
                 daily_work_hours, preferred_time, rest_frequency, accommodation_needs,
                 education_level, school_name, major,
                 career_years, recent_company, recent_job_title, experience_summary,
                 desired_job, work_pref, resume_path,
                 disability_visibility, consent_sensitive, consented_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))""",
                (uid, disability_type_id, severity, gender, birth_year, region_id,
                 mobility_type, commute_max_minutes,
                 communication_pref, assistive_tech,
                 daily_work_hours, preferred_time, rest_frequency, accommodation_needs,
                 education_level, school_name, major,
                 career_years, recent_company, recent_job_title, experience_summary,
                 desired_job, work_pref, resume_path,
                 disability_visibility, consent_sensitive))
        conn.commit()

        # 자격증 저장 (기존 삭제 후 재삽입)
        cert_names = form.getlist("cert_name")
        cert_dates = form.getlist("cert_date")
        cert_orgs = form.getlist("cert_org")
        valid_certs = [(n, d, o) for n, d, o in zip(cert_names, cert_dates, cert_orgs) if n.strip()]
        if valid_certs:
            conn.execute("DELETE FROM seeker_certifications WHERE user_id=?", (uid,))
            for n, d, o in valid_certs:
                conn.execute(
                    "INSERT INTO seeker_certifications (user_id, cert_name, cert_date, issuing_org) VALUES (?,?,?,?)",
                    (uid, n.strip(), d.strip(), o.strip()),
                )
            conn.commit()

    finally:
        conn.close()
    return RedirectResponse(url="/profile?success=1", status_code=303)


@router.get("/jobs", response_class=HTMLResponse)
async def job_search(
    request: Request,
    q: str = Query(None),
    region_id: int = Query(None),
    sido: str = Query(None),
    employment_type: str = Query(None),
    remote: str = Query(None),
    category: str = Query(None),
    max_hours: str = Query(None),
    accommodation: str = Query(None),
    disability_type: str = Query(None),
    severity: str = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        categories = conn.execute("SELECT * FROM job_categories ORDER BY major_code, minor_code").fetchall()
        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
        sql = (
            "SELECT jp.*, c.company_name, c.id AS company_db_id, jc.minor_name_ko AS category_name, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM job_postings jp "
            "JOIN companies c ON jp.company_id=c.id "
            "LEFT JOIN job_categories jc ON jp.category_id=jc.id "
            "LEFT JOIN regions r ON jp.region_id=r.id "
            "WHERE jp.status='open'"
        )
        params = []
        if q:
            sql += " AND (jp.title LIKE ? OR jp.description LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if region_id:
            sql += " AND jp.region_id=?"
            params.append(region_id)
        elif sido:
            sql += " AND r.sido=?"
            params.append(sido)
        if employment_type:
            sql += " AND jp.employment_type=?"
            params.append(employment_type)
        if remote:
            sql += " AND jp.remote_available=1"
        if category:
            sql += " AND jp.category_id=?"
            params.append(int(category))
        if max_hours:
            sql += " AND jp.min_work_hours<=?"
            params.append(int(max_hours))
        if accommodation:
            sql += " AND jp.accommodations_provided LIKE ?"
            params.append(f"%{accommodation}%")
        if disability_type:
            sql += " AND jp.preferred_disability LIKE ?"
            params.append(f"%{disability_type}%")
        if severity:
            sql += " AND (jp.preferred_severity=? OR jp.preferred_severity='무관')"
            params.append(severity)
        sql += " ORDER BY jp.created_at DESC"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        jobs_raw = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
        bookmarked_ids = set()
        bookmark_rows = conn.execute(
            "SELECT job_id FROM bookmarks WHERE user_id=?", (user["id"],)
        ).fetchall()
        for row in bookmark_rows:
            bookmarked_ids.add(row["job_id"])
        seeker_profile = conn.execute(
            "SELECT accommodation_needs FROM seeker_profiles WHERE user_id=?",
            (user["id"],),
        ).fetchone()
        seeker_needs = []
        if seeker_profile and seeker_profile["accommodation_needs"]:
            try:
                seeker_needs = json.loads(seeker_profile["accommodation_needs"])
            except (json.JSONDecodeError, TypeError):
                pass
        seeker_needs_set = set(seeker_needs)
        jobs = []
        for row in jobs_raw:
            job = dict(row)
            try:
                provided = json.loads(job.get("accommodations_provided") or "[]")
            except (json.JSONDecodeError, TypeError):
                provided = []
            job["accommodation_match_count"] = len(seeker_needs_set & set(provided))
            jobs.append(job)
    finally:
        conn.close()
    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if sido: qs_parts.append(f"sido={sido}")
    if region_id: qs_parts.append(f"region_id={region_id}")
    if employment_type: qs_parts.append(f"employment_type={employment_type}")
    if remote: qs_parts.append(f"remote={remote}")
    if category: qs_parts.append(f"category={category}")
    if max_hours: qs_parts.append(f"max_hours={max_hours}")
    if accommodation: qs_parts.append(f"accommodation={accommodation}")
    if disability_type: qs_parts.append(f"disability_type={disability_type}")
    if severity: qs_parts.append(f"severity={severity}")
    base_qs = "&".join(qs_parts)
    return templates.TemplateResponse(
        request=request, name="seeker/jobs.html", context={
            "request": request, "page_title": "공고 검색",
            "user_name": user["name"], "user_role": "seeker",
            "jobs": jobs,
            "bookmarked_ids": bookmarked_ids,
            "seeker_needs": seeker_needs,
            "employment_types": EMPLOYMENT_TYPES,
            "categories": categories,
            "q": q or "",
            "selected_sido": sido or "",
            "selected_region_id": region_id or "",
            "selected_type": employment_type or "",
            "selected_category": category or "",
            "remote_checked": bool(remote),
            "selected_max_hours": int(max_hours) if max_hours else "",
            "selected_accommodation": accommodation or "",
            "accommodation_options": ACCOMMODATION_OPTIONS,
            "disability_types": disability_types,
            "selected_disability_type": disability_type or "",
            "selected_severity": severity or "",
            "pagination": pagination, "base_qs": base_qs,
        }
    )


@router.get("/apply/{job_id}", response_class=HTMLResponse)
async def apply_form(request: Request, job_id: int):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        job = conn.execute(
            "SELECT * FROM job_postings WHERE id=? AND status='open'", (job_id,)
        ).fetchone()
        if job is None:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
        profile = conn.execute(
            "SELECT * FROM seeker_profiles WHERE user_id=?",
            (user["id"],),
        ).fetchone()
        if profile is None:
            return RedirectResponse(url="/profile?error=incomplete&msg=프로필을+먼저+완성해주세요.", status_code=303)
        if not profile["consent_sensitive"]:
            return RedirectResponse(url="/profile?error=consent", status_code=303)
        missing = []
        if not profile["disability_type_id"]:
            missing.append("장애유형")
        if not profile["severity"]:
            missing.append("장애정도")
        accommodation_needs = profile["accommodation_needs"]
        try:
            parsed_needs = json.loads(accommodation_needs) if accommodation_needs else []
        except (json.JSONDecodeError, TypeError):
            parsed_needs = []
        if not parsed_needs:
            missing.append("편의제공 필요사항")
        if missing:
            msg = "프로필을+먼저+완성해주세요."
            return RedirectResponse(url=f"/profile?error=incomplete&msg={msg}", status_code=303)
        already_applied = conn.execute(
            "SELECT id FROM candidacies WHERE job_id=? AND seeker_user_id=?",
            (job_id, user["id"]),
        ).fetchone()
        company = conn.execute(
            "SELECT company_name FROM companies WHERE id=?", (job["company_id"],)
        ).fetchone()
        company_name = company["company_name"] if company else ""
        disability_type = conn.execute(
            "SELECT name FROM disability_types WHERE id=?", (profile["disability_type_id"],)
        ).fetchone()
        disability_name = disability_type["name"] if disability_type else ""
        resumes = conn.execute(
            "SELECT id, name, is_default FROM resumes WHERE user_id=? ORDER BY is_default DESC, updated_at DESC",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/apply_form.html", context={
            "request": request, "page_title": "지원서 작성",
            "user_name": user["name"], "user_role": "seeker",
            "job": job,
            "already_applied": already_applied is not None,
            "profile": profile,
            "company_name": company_name,
            "disability_name": disability_name,
            "resumes": resumes,
        }
    )


@router.post("/apply/{job_id}")
async def apply_submit(
    request: Request,
    job_id: int,
    cover_letter: str = Form(""),
    resume_id: int = Form(0),
):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        job = conn.execute(
            "SELECT id FROM job_postings WHERE id=? AND status='open'", (job_id,)
        ).fetchone()
        if job is None:
            return RedirectResponse(url="/jobs", status_code=303)
        try:
            resume_snapshot = ""
            if resume_id:
                snapshot_resume = conn.execute(
                    "SELECT id FROM resumes WHERE id=? AND user_id=?",
                    (resume_id, user["id"]),
                ).fetchone()
                if snapshot_resume:
                    resume_snapshot = build_resume_snapshot(conn, resume_id)
            cur = conn.execute(
                """INSERT INTO candidacies (job_id, seeker_user_id, source, status, cover_letter, resume_id, resume_snapshot)
                   VALUES (?,?,'direct','pending',?,?,?)""",
                (job_id, user["id"], cover_letter, resume_id or None, resume_snapshot),
            )
            conn.execute(
                """INSERT INTO status_history (candidacy_id, from_status, to_status, actor_id, comment)
                   VALUES (?,?,?,?,?)""",
                (cur.lastrowid, "", "pending", user["id"], "직접 지원"),
            )
            job_row = conn.execute(
                "SELECT jp.title, c.user_id as company_user_id FROM job_postings jp "
                "JOIN companies c ON jp.company_id=c.id WHERE jp.id=?", (job_id,),
            ).fetchone()
            if job_row:
                create_notification(
                    conn, job_row["company_user_id"],
                    f"[{job_row['title']}] 새로운 지원이 있습니다.",
                    f"/company/jobs/{job_id}/applicants",
                )
            conn.commit()
        except Exception:
            log.exception("지원서 제출 실패: job_id=%s user_id=%s", job_id, user["id"])
            conn.rollback()
            return RedirectResponse(url=f"/apply/{job_id}?error=duplicate", status_code=303)
    finally:
        conn.close()
    return RedirectResponse(url="/applications", status_code=303)


@router.get("/applications", response_class=HTMLResponse)
async def applications_list(request: Request):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        applications = conn.execute(
            """SELECT c.id, c.status, c.created_at, c.source,
                      jp.title, jp.id AS job_id,
                      co.company_name
               FROM candidacies c
               JOIN job_postings jp ON c.job_id=jp.id
               JOIN companies co ON jp.company_id=co.id
               WHERE c.seeker_user_id=?
               ORDER BY c.created_at DESC""",
            (user["id"],),
        ).fetchall()
        history_map = {}
        for app in applications:
            history = conn.execute(
                """SELECT to_status, created_at, comment
                   FROM status_history
                   WHERE candidacy_id=?
                   ORDER BY id ASC""",
                (app["id"],),
            ).fetchall()
            history_map[app["id"]] = history
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/applications.html", context={
            "request": request, "page_title": "내 지원 현황",
            "user_name": user["name"], "user_role": "seeker",
            "applications": applications,
            "history_map": history_map,
            "status_labels": STATUS_LABELS,
        }
    )


@router.post("/applications/{candidacy_id}/withdraw")
async def withdraw_application(request: Request, candidacy_id: int):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        cand = conn.execute(
            "SELECT * FROM candidacies WHERE id=? AND seeker_user_id=?",
            (candidacy_id, user["id"]),
        ).fetchone()
        if cand and cand["status"] not in ("hired", "rejected", "withdrawn"):
            conn.execute(
                "UPDATE candidacies SET status='withdrawn', updated_at=datetime('now','localtime') WHERE id=?",
                (candidacy_id,),
            )
            conn.execute(
                """INSERT INTO status_history (candidacy_id, from_status, to_status, actor_id, comment)
                   VALUES (?,?,?,?,?)""",
                (candidacy_id, cand["status"], "withdrawn", user["id"], "지원 취소"),
            )
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/applications", status_code=303)


@router.get("/proposals", response_class=HTMLResponse)
async def proposals_list(request: Request):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        proposals = conn.execute(
            """SELECT c.id, c.job_id, c.match_stage, c.created_at,
                      jp.title AS job_title, jp.employment_type,
                      r.sido AS region_sido, r.sigungu AS region_sigungu,
                      co.company_name
               FROM candidacies c
               JOIN job_postings jp ON c.job_id = jp.id
               JOIN companies co ON jp.company_id = co.id
               LEFT JOIN regions r ON jp.region_id = r.id
               WHERE c.seeker_user_id = ?
                 AND c.source = 'operator_matched'
                 AND c.match_stage IN ('proposed', 'accepted')
               ORDER BY c.created_at DESC""",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/proposals.html", context={
            "request": request, "page_title": "매칭 제안",
            "user_name": user["name"], "user_role": "seeker",
            "proposals": proposals,
        }
    )


@router.post("/proposals/{candidacy_id}/respond")
async def proposal_respond(
    request: Request,
    candidacy_id: int,
    action: str = Form(...),
):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        cand = conn.execute(
            """SELECT * FROM candidacies
               WHERE id=? AND seeker_user_id=?
                 AND source='operator_matched' AND match_stage='proposed'""",
            (candidacy_id, user["id"]),
        ).fetchone()
        if cand:
            history = conn.execute(
                "SELECT actor_id FROM status_history WHERE candidacy_id=? ORDER BY id ASC LIMIT 1",
                (candidacy_id,),
            ).fetchone()
            job = conn.execute(
                "SELECT jp.title FROM job_postings jp JOIN candidacies c ON c.job_id=jp.id WHERE c.id=?",
                (candidacy_id,),
            ).fetchone()
            job_title = job["title"] if job else "공고"
            if action == "accept":
                conn.execute(
                    """UPDATE candidacies SET match_stage='seeker_confirmed',
                       updated_at=datetime('now','localtime') WHERE id=?""",
                    (candidacy_id,),
                )
                conn.execute(
                    """INSERT INTO status_history
                       (candidacy_id, from_status, to_status, actor_id, comment)
                       VALUES (?, ?, ?, ?, '구직자 매칭 수락')""",
                    (candidacy_id, cand["status"], cand["status"], user["id"]),
                )
                if history:
                    create_notification(conn, history["actor_id"], f"[{job_title}] 구직자가 매칭 제안을 수락했습니다.", "/op/candidacies")
            elif action == "reject":
                conn.execute(
                    """UPDATE candidacies SET status='withdrawn',
                       updated_at=datetime('now','localtime') WHERE id=?""",
                    (candidacy_id,),
                )
                conn.execute(
                    """INSERT INTO status_history
                       (candidacy_id, from_status, to_status, actor_id, comment)
                       VALUES (?, ?, 'withdrawn', ?, '구직자 매칭 거절')""",
                    (candidacy_id, cand["status"], user["id"]),
                )
                if history:
                    create_notification(conn, history["actor_id"], f"[{job_title}] 구직자가 매칭 제안을 거절했습니다.", "/op/candidacies")
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/proposals", status_code=303)


@router.post("/bookmarks/{job_id}/toggle")
async def toggle_bookmark(request: Request, job_id: int):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        existing = conn.execute(
            "SELECT id FROM bookmarks WHERE user_id=? AND job_id=?",
            (user["id"], job_id),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM bookmarks WHERE id=?", (existing["id"],))
            bookmarked = False
        else:
            conn.execute(
                "INSERT INTO bookmarks (user_id, job_id) VALUES (?,?)",
                (user["id"], job_id),
            )
            bookmarked = True
        conn.commit()
    finally:
        conn.close()
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"bookmarked": bookmarked})
    referer = request.headers.get("referer", "/jobs")
    return RedirectResponse(url=referer, status_code=303)


@router.get("/bookmarks", response_class=HTMLResponse)
async def bookmarks_list(request: Request):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        jobs = conn.execute(
            """SELECT jp.*, c.company_name,
                      jc.minor_name_ko AS category_name,
                      r.sido AS region_sido, r.sigungu AS region_sigungu,
                      b.created_at AS bookmarked_at
               FROM bookmarks b
               JOIN job_postings jp ON b.job_id=jp.id
               JOIN companies c ON jp.company_id=c.id
               LEFT JOIN job_categories jc ON jp.category_id=jc.id
               LEFT JOIN regions r ON jp.region_id=r.id
               WHERE b.user_id=?
               ORDER BY b.created_at DESC""",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/bookmarks.html", context={
            "request": request, "page_title": "저장한 공고",
            "user_name": user["name"], "user_role": "seeker",
            "jobs": jobs,
        }
    )


@router.get("/recent", response_class=HTMLResponse)
async def recent_views_list(request: Request):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        jobs = conn.execute(
            """SELECT jp.*, c.company_name,
                      jc.minor_name_ko AS category_name,
                      r.sido AS region_sido, r.sigungu AS region_sigungu,
                      rv.viewed_at
               FROM recent_views rv
               JOIN job_postings jp ON rv.job_id=jp.id
               JOIN companies c ON jp.company_id=c.id
               LEFT JOIN job_categories jc ON jp.category_id=jc.id
               LEFT JOIN regions r ON jp.region_id=r.id
               WHERE rv.user_id=?
               ORDER BY rv.viewed_at DESC
               LIMIT 20""",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/recent.html", context={
            "request": request, "page_title": "최근 본 공고",
            "user_name": user["name"], "user_role": "seeker",
            "jobs": jobs,
        }
    )


@router.get("/companies/{company_id}", response_class=HTMLResponse)
async def company_detail(request: Request, company_id: int):
    user = require_role(request, "seeker", "operator", "manager")
    conn = get_sqlite()
    try:
        company = conn.execute(
            """SELECT c.*, r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM companies c
               LEFT JOIN regions r ON c.region_id=r.id
               WHERE c.id=?""",
            (company_id,),
        ).fetchone()
        if company is None:
            raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다.")
        open_jobs = conn.execute(
            """SELECT jp.*, jc.minor_name_ko AS category_name,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM job_postings jp
               LEFT JOIN job_categories jc ON jp.category_id=jc.id
               LEFT JOIN regions r ON jp.region_id=r.id
               WHERE jp.company_id=? AND jp.status='open'
               ORDER BY jp.created_at DESC""",
            (company_id,),
        ).fetchall()
        accessibility_facilities = []
        if company["accessibility_facilities"]:
            try:
                accessibility_facilities = json.loads(company["accessibility_facilities"])
            except (json.JSONDecodeError, TypeError):
                pass
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/company_detail.html", context={
            "request": request, "page_title": company["company_name"],
            "user_name": user["name"], "user_role": "seeker",
            "company": company,
            "open_jobs": open_jobs,
            "accessibility_facilities": accessibility_facilities,
        }
    )


@router.get("/profile/views", response_class=HTMLResponse)
async def profile_views(request: Request):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        views = conn.execute(
            """SELECT al.created_at, al.purpose,
                      u.name AS viewer_name,
                      c.company_name
               FROM access_log al
               JOIN users u ON al.viewer_id = u.id
               LEFT JOIN companies c ON u.id = c.user_id
               WHERE al.seeker_user_id = ?
               ORDER BY al.created_at DESC
               LIMIT 50""",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/profile_views.html", context={
            "request": request, "page_title": "프로필 열람 현황",
            "user_name": user["name"], "user_role": "seeker",
            "views": views,
        }
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: int):
    user = require_role(request, "seeker")
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
            "WHERE jp.id=? AND jp.status='open'",
            (job_id,)
        ).fetchone()
        d_day = None
        if job and job['deadline']:
            try:
                deadline_date = date.fromisoformat(job['deadline'])
                d_day = (deadline_date - date.today()).days
            except ValueError:
                pass
        profile = conn.execute(
            "SELECT accommodation_needs FROM seeker_profiles WHERE user_id=?",
            (user["id"],),
        ).fetchone()
        seeker_needs = json.loads(profile["accommodation_needs"]) if profile and profile["accommodation_needs"] else []
        accommodations_provided = json.loads(job["accommodations_provided"]) if job and job["accommodations_provided"] else []
        preferred_disability = json.loads(job["preferred_disability"]) if job and job["preferred_disability"] else []
        is_bookmarked = conn.execute(
            "SELECT 1 FROM bookmarks WHERE user_id=? AND job_id=?",
            (user["id"], job_id),
        ).fetchone() is not None
        already_applied = conn.execute(
            "SELECT 1 FROM candidacies WHERE job_id=? AND seeker_user_id=?",
            (job_id, user["id"]),
        ).fetchone() is not None
        similar_jobs = []
        company_jobs = []
        if job is not None:
            conn.execute(
                "INSERT INTO recent_views (user_id, job_id, viewed_at) VALUES (?,?,datetime('now','localtime')) "
                "ON CONFLICT(user_id, job_id) DO UPDATE SET viewed_at=datetime('now','localtime')",
                (user["id"], job_id),
            )
            conn.commit()
            # 같은 직무 카테고리 또는 같은 지역 공고
            similar_sql = (
                "SELECT jp.id, jp.title, jp.employment_type, jp.salary, jp.deadline, "
                "c.company_name, r.sido AS region_sido, r.sigungu AS region_sigungu "
                "FROM job_postings jp "
                "JOIN companies c ON jp.company_id=c.id "
                "LEFT JOIN regions r ON jp.region_id=r.id "
                "WHERE jp.status='open' AND jp.id!=?"
            )
            similar_params = [job_id]
            conditions = []
            if job["category_id"]:
                conditions.append("jp.category_id=?")
                similar_params.append(job["category_id"])
            if job["region_id"]:
                conditions.append("jp.region_id=?")
                similar_params.append(job["region_id"])
            if conditions:
                similar_sql += " AND (" + " OR ".join(conditions) + ")"
                similar_sql += " ORDER BY jp.created_at DESC LIMIT 4"
                similar_jobs = conn.execute(similar_sql, similar_params).fetchall()
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
    if job is None:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    return templates.TemplateResponse(
        request=request, name="seeker/job_detail.html", context={
            "request": request, "page_title": job["title"],
            "user_name": user["name"], "user_role": "seeker",
            "job": job,
            "accommodations_provided": accommodations_provided,
            "preferred_disability": preferred_disability,
            "seeker_needs": seeker_needs,
            "is_bookmarked": is_bookmarked,
            "similar_jobs": similar_jobs,
            "d_day": d_day,
            "already_applied": already_applied,
            "company_jobs": company_jobs,
        }
    )


# --- 검색 알림 ---

_SEARCH_FILTER_KEYS = [
    'q', 'sido', 'region_id', 'employment_type', 'remote',
    'category', 'max_hours', 'accommodation', 'disability_type', 'severity',
]


def _build_search_sql(filters):
    sql = (
        "SELECT jp.id, jp.created_at FROM job_postings jp "
        "LEFT JOIN regions r ON jp.region_id=r.id "
        "WHERE jp.status='open'"
    )
    params = []
    if filters.get('q'):
        sql += " AND (jp.title LIKE ? OR jp.description LIKE ?)"
        params += [f"%{filters['q']}%", f"%{filters['q']}%"]
    if filters.get('region_id'):
        sql += " AND jp.region_id=?"
        params.append(int(filters['region_id']))
    elif filters.get('sido'):
        sql += " AND r.sido=?"
        params.append(filters['sido'])
    if filters.get('employment_type'):
        sql += " AND jp.employment_type=?"
        params.append(filters['employment_type'])
    if filters.get('remote'):
        sql += " AND jp.remote_available=1"
    if filters.get('category'):
        sql += " AND jp.category_id=?"
        params.append(int(filters['category']))
    if filters.get('max_hours'):
        sql += " AND jp.min_work_hours<=?"
        params.append(int(filters['max_hours']))
    if filters.get('accommodation'):
        sql += " AND jp.accommodations_provided LIKE ?"
        params.append(f"%{filters['accommodation']}%")
    if filters.get('disability_type'):
        sql += " AND jp.preferred_disability LIKE ?"
        params.append(f"%{filters['disability_type']}%")
    if filters.get('severity'):
        sql += " AND (jp.preferred_severity=? OR jp.preferred_severity='무관')"
        params.append(filters['severity'])
    return sql, params


@router.post("/saved-searches")
async def save_search(request: Request):
    user = require_role(request, "seeker")
    form = await request.form()
    filters = {k: form.get(k, "") for k in _SEARCH_FILTER_KEYS if form.get(k, "")}

    parts = []
    if filters.get('q'):
        parts.append(f"'{filters['q']}'")
    if filters.get('sido'):
        parts.append(filters['sido'])
    if filters.get('employment_type'):
        parts.append(filters['employment_type'])
    if filters.get('disability_type'):
        parts.append(filters['disability_type'])
    name = form.get("alert_name", "").strip() or (' / '.join(parts) if parts else '전체 공고')

    conn = get_sqlite()
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM saved_searches WHERE user_id=?",
            (user["id"],),
        ).fetchone()[0]
        if cnt >= 10:
            referer = request.headers.get("referer", "/jobs")
            return RedirectResponse(url=referer, status_code=303)
        conn.execute(
            "INSERT INTO saved_searches (user_id, name, filters) VALUES (?,?,?)",
            (user["id"], name, json.dumps(filters, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    referer = request.headers.get("referer", "/jobs")
    return RedirectResponse(url=referer, status_code=303)


@router.get("/saved-searches", response_class=HTMLResponse)
async def saved_searches_list(request: Request):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        searches = conn.execute(
            "SELECT * FROM saved_searches WHERE user_id=? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
        cat_map = {
            str(r["id"]): r["minor_name_ko"]
            for r in conn.execute("SELECT id, minor_name_ko FROM job_categories").fetchall()
        }
        region_map = {
            str(r["id"]): f"{r['sido']} {r['sigungu']}"
            for r in conn.execute("SELECT id, sido, sigungu FROM regions").fetchall()
        }
        hours_label = {"4": "4시간 이하", "6": "6시간 이하", "8": "8시간"}

        search_data = []
        for s in searches:
            filters = json.loads(s["filters"]) if s["filters"] else {}
            last_checked = s["last_checked_at"] or s["created_at"]
            count_sql, count_params = _build_search_sql(filters)
            count_sql = f"SELECT COUNT(*) FROM ({count_sql} AND jp.created_at > ?)"
            count_params.append(last_checked)
            new_count = conn.execute(count_sql, count_params).fetchone()[0]
            qs = urlencode(filters)

            labels = []
            if filters.get("q"):
                labels.append(f"'{filters['q']}'")
            if filters.get("sido"):
                labels.append(filters["sido"])
            if filters.get("region_id"):
                lbl = region_map.get(str(filters["region_id"]))
                if lbl:
                    labels.append(lbl)
            if filters.get("employment_type"):
                labels.append(filters["employment_type"])
            if filters.get("category"):
                lbl = cat_map.get(str(filters["category"]))
                if lbl:
                    labels.append(lbl)
            if filters.get("max_hours"):
                labels.append(hours_label.get(str(filters["max_hours"]), f"{filters['max_hours']}시간"))
            if filters.get("disability_type"):
                labels.append(filters["disability_type"])
            if filters.get("severity"):
                labels.append(filters["severity"])
            if filters.get("accommodation"):
                labels.append(filters["accommodation"])
            if filters.get("remote"):
                labels.append("재택가능")

            search_data.append({
                "id": s["id"],
                "name": s["name"],
                "labels": labels,
                "new_count": new_count,
                "search_url": f"/jobs?{qs}" if qs else "/jobs",
                "created_at": s["created_at"],
            })
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/saved_searches.html", context={
            "request": request, "page_title": "검색 알림",
            "user_name": user["name"], "user_role": "seeker",
            "searches": search_data,
        }
    )


@router.post("/saved-searches/{search_id}/check")
async def mark_search_checked(request: Request, search_id: int):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE saved_searches SET last_checked_at=datetime('now','localtime') "
            "WHERE id=? AND user_id=?",
            (search_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/saved-searches", status_code=303)


@router.delete("/saved-searches/{search_id}")
async def delete_saved_search(request: Request, search_id: int):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        conn.execute(
            "DELETE FROM saved_searches WHERE id=? AND user_id=?",
            (search_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"redirect": "/saved-searches"})
