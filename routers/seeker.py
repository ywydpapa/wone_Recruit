import json
import os
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from core.logger import log
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import (
    EMPLOYMENT_TYPES, STATUS_LABELS,
    EDUCATION_LEVELS, MOBILITY_TYPES, COMMUTE_OPTIONS,
    COMMUNICATION_OPTIONS, ASSISTIVE_TECH_OPTIONS,
    DAILY_HOURS_OPTIONS, PREFERRED_TIME_OPTIONS,
    REST_FREQUENCY_OPTIONS, ACCOMMODATION_OPTIONS,
    EDUCATION_LEVELS_DETAIL, GRADUATION_STATUS, GPA_SCALES,
    CAREER_EMPLOYMENT_TYPES, LANGUAGE_LIST, LANGUAGE_LEVELS,
    AWARD_CATEGORIES, PORTFOLIO_LINK_TYPES,
)
from core.upload import save_upload
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
async def profile_form(request: Request, error: str = "", success: str = "", msg: str = ""):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        profile = conn.execute("SELECT * FROM seeker_profiles WHERE user_id=?", (user["user_id"],)).fetchone()
        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
        certifications = conn.execute(
            "SELECT * FROM seeker_certifications WHERE user_id=? ORDER BY id",
            (user["user_id"],),
        ).fetchall()
        education_list = conn.execute(
            "SELECT * FROM education_history WHERE user_id=? ORDER BY sort_order",
            (user["user_id"],),
        ).fetchall()
        career_list = conn.execute(
            "SELECT * FROM career_history WHERE user_id=? ORDER BY sort_order",
            (user["user_id"],),
        ).fetchall()
        language_list = conn.execute(
            "SELECT * FROM language_skills WHERE user_id=? ORDER BY sort_order",
            (user["user_id"],),
        ).fetchall()
        awards_list = conn.execute(
            "SELECT * FROM awards_activities WHERE user_id=? ORDER BY sort_order",
            (user["user_id"],),
        ).fetchall()
        portfolio_list = conn.execute(
            "SELECT * FROM portfolio_links WHERE user_id=? ORDER BY sort_order",
            (user["user_id"],),
        ).fetchall()
        intro_list = conn.execute(
            "SELECT * FROM self_intro_items WHERE user_id=? ORDER BY sort_order",
            (user["user_id"],),
        ).fetchall()
        intro_presets = conn.execute(
            "SELECT * FROM self_intro_presets WHERE is_active=1 ORDER BY sort_order",
        ).fetchall()
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
            "user_name": user["user_name"], "user_role": "seeker",
            "user": user,
            "profile": profile, "disability_types": disability_types,
            "certifications": certifications,
            "education_list": education_list,
            "career_list": career_list,
            "language_list": language_list,
            "awards_list": awards_list,
            "portfolio_list": portfolio_list,
            "intro_list": intro_list,
            "intro_presets": intro_presets,
            "selected_sido": selected_sido,
            "communication_pref": communication_pref,
            "assistive_tech": assistive_tech,
            "accommodation_needs": accommodation_needs,
            "education_levels": EDUCATION_LEVELS,
            "education_levels_detail": EDUCATION_LEVELS_DETAIL,
            "graduation_status_list": GRADUATION_STATUS,
            "gpa_scales": GPA_SCALES,
            "career_employment_types": CAREER_EMPLOYMENT_TYPES,
            "language_options": LANGUAGE_LIST,
            "language_levels": LANGUAGE_LEVELS,
            "award_categories": AWARD_CATEGORIES,
            "portfolio_link_types": PORTFOLIO_LINK_TYPES,
            "mobility_types": MOBILITY_TYPES,
            "commute_options": COMMUTE_OPTIONS,
            "communication_options": COMMUNICATION_OPTIONS,
            "assistive_tech_options": ASSISTIVE_TECH_OPTIONS,
            "daily_hours_options": DAILY_HOURS_OPTIONS,
            "preferred_time_options": PREFERRED_TIME_OPTIONS,
            "rest_frequency_options": REST_FREQUENCY_OPTIONS,
            "accommodation_options": ACCOMMODATION_OPTIONS,
            "error": error, "success": success, "msg": msg,
        }
    )


def _calc_education_level(rows):
    rank = {'대학원(박사)': 5, '대학원(석사)': 4, '대학교(4년)': 3, '전문대(2/3년)': 2, '고등학교': 1}
    level_map = {'대학원(박사)': '박사', '대학원(석사)': '석사', '대학교(4년)': '대졸', '전문대(2/3년)': '전문대졸', '고등학교': '고졸'}
    best = ''
    best_rank = 0
    for r in rows:
        lv = r.get('education_level', '')
        if rank.get(lv, 0) > best_rank:
            best_rank = rank[lv]
            best = level_map.get(lv, '')
    return best


def _calc_career_years(rows):
    total_months = 0
    for r in rows:
        start = r.get('start_date', '')
        end = r.get('end_date', '')
        if not start:
            continue
        try:
            s = datetime.strptime(start, "%Y-%m")
            if end:
                e = datetime.strptime(end, "%Y-%m")
            else:
                e = datetime.now()
            diff = (e.year - s.year) * 12 + (e.month - s.month)
            if diff > 0:
                total_months += diff
        except ValueError:
            continue
    return max(0, round(total_months / 12))


@router.post("/profile")
async def profile_save(request: Request, resume: UploadFile = File(None)):
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
    desired_job = form.get("desired_job", "")
    work_pref = form.get("work_pref", "무관")
    mobility_type = form.get("mobility_type", "")
    commute_max_minutes = int(form.get("commute_max_minutes") or 0) or None
    daily_work_hours = int(form.get("daily_work_hours") or 8)
    preferred_time = form.get("preferred_time", "풀타임")
    rest_frequency = form.get("rest_frequency", "불필요")

    disability_visibility = form.get("disability_visibility", "manager_only")
    communication_pref = json.dumps(form.getlist("communication_pref"), ensure_ascii=False)
    assistive_tech = json.dumps(form.getlist("assistive_tech"), ensure_ascii=False)
    accommodation_needs = json.dumps(form.getlist("accommodation_needs"), ensure_ascii=False)

    resume_path = ""
    if resume and resume.filename:
        resume_path = await save_upload(
            resume, "resumes", user["user_id"],
            ["application/pdf"], 10 * 1024 * 1024,
        )

    uid = user["user_id"]
    conn = get_sqlite()
    try:
        existing = conn.execute("SELECT id, resume_path FROM seeker_profiles WHERE user_id=?", (uid,)).fetchone()
        if not resume_path and existing:
            resume_path = existing["resume_path"] or ""

        # 학력
        conn.execute("DELETE FROM education_history WHERE user_id=?", (uid,))
        edu_levels = form.getlist("edu_level")
        edu_schools = form.getlist("edu_school")
        edu_majors = form.getlist("edu_major")
        edu_grad_statuses = form.getlist("edu_grad_status")
        edu_starts = form.getlist("edu_start")
        edu_ends = form.getlist("edu_end")
        edu_gpas = form.getlist("edu_gpa")
        edu_gpa_scales = form.getlist("edu_gpa_scale")
        edu_rows = []
        for i in range(len(edu_levels)):
            lv = edu_levels[i].strip() if i < len(edu_levels) else ""
            school = edu_schools[i].strip() if i < len(edu_schools) else ""
            if not lv and not school:
                continue
            row = {
                "education_level": lv,
                "school_name": school,
                "major": edu_majors[i].strip() if i < len(edu_majors) else "",
                "graduation_status": edu_grad_statuses[i].strip() if i < len(edu_grad_statuses) else "",
                "start_date": edu_starts[i].strip() if i < len(edu_starts) else "",
                "end_date": edu_ends[i].strip() if i < len(edu_ends) else "",
                "gpa": edu_gpas[i].strip() if i < len(edu_gpas) else "",
                "gpa_scale": edu_gpa_scales[i].strip() if i < len(edu_gpa_scales) else "",
                "is_transfer": 1 if form.get(f"edu_transfer_{i}") else 0,
            }
            edu_rows.append(row)
            conn.execute(
                """INSERT INTO education_history
                   (user_id, sort_order, education_level, school_name, major, start_date, end_date,
                    graduation_status, gpa, gpa_scale, is_transfer)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (uid, i, row["education_level"], row["school_name"], row["major"],
                 row["start_date"], row["end_date"], row["graduation_status"],
                 row["gpa"], row["gpa_scale"], row["is_transfer"]),
            )

        # 경력
        conn.execute("DELETE FROM career_history WHERE user_id=?", (uid,))
        car_companies = form.getlist("car_company")
        car_depts = form.getlist("car_dept")
        car_positions = form.getlist("car_position")
        car_emp_types = form.getlist("car_emp_type")
        car_starts = form.getlist("car_start")
        car_ends = form.getlist("car_end")
        car_descs = form.getlist("car_desc")
        career_rows = []
        for i in range(len(car_companies)):
            company = car_companies[i].strip()
            if not company:
                continue
            is_current = 1 if form.get(f"car_current_{i}") else 0
            row = {
                "start_date": car_starts[i].strip() if i < len(car_starts) else "",
                "end_date": "" if is_current else (car_ends[i].strip() if i < len(car_ends) else ""),
            }
            career_rows.append(row)
            conn.execute(
                """INSERT INTO career_history
                   (user_id, sort_order, company_name, department, position, start_date, end_date,
                    is_current, employment_type, description)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (uid, i, company,
                 car_depts[i].strip() if i < len(car_depts) else "",
                 car_positions[i].strip() if i < len(car_positions) else "",
                 row["start_date"], row["end_date"], is_current,
                 car_emp_types[i].strip() if i < len(car_emp_types) else "",
                 car_descs[i].strip() if i < len(car_descs) else ""),
            )

        education_level = _calc_education_level(edu_rows)
        career_years = _calc_career_years(career_rows)

        # 자격증
        conn.execute("DELETE FROM seeker_certifications WHERE user_id=?", (uid,))
        cert_names = form.getlist("cert_name")
        cert_dates = form.getlist("cert_date")
        cert_orgs = form.getlist("cert_org")
        for i in range(len(cert_names)):
            name = cert_names[i].strip()
            if not name:
                continue
            date = cert_dates[i].strip() if i < len(cert_dates) else ""
            org = cert_orgs[i].strip() if i < len(cert_orgs) else ""
            conn.execute(
                "INSERT INTO seeker_certifications (user_id, cert_name, cert_date, issuing_org) VALUES (?,?,?,?)",
                (uid, name, date, org),
            )

        # 어학
        conn.execute("DELETE FROM language_skills WHERE user_id=?", (uid,))
        lang_languages = form.getlist("lang_language")
        lang_tests = form.getlist("lang_test")
        lang_scores = form.getlist("lang_score")
        lang_levels = form.getlist("lang_level")
        lang_dates = form.getlist("lang_date")
        for i in range(len(lang_languages)):
            language = lang_languages[i].strip()
            test = lang_tests[i].strip() if i < len(lang_tests) else ""
            if not language and not test:
                continue
            conn.execute(
                """INSERT INTO language_skills
                   (user_id, sort_order, language, test_name, score, level, test_date)
                   VALUES (?,?,?,?,?,?,?)""",
                (uid, i, language, test,
                 lang_scores[i].strip() if i < len(lang_scores) else "",
                 lang_levels[i].strip() if i < len(lang_levels) else "",
                 lang_dates[i].strip() if i < len(lang_dates) else ""),
            )

        # 수상/활동
        conn.execute("DELETE FROM awards_activities WHERE user_id=?", (uid,))
        award_cats = form.getlist("award_category")
        award_titles = form.getlist("award_title")
        award_orgs = form.getlist("award_org")
        award_dates = form.getlist("award_date")
        award_descs = form.getlist("award_desc")
        for i in range(len(award_titles)):
            title = award_titles[i].strip()
            if not title:
                continue
            conn.execute(
                """INSERT INTO awards_activities
                   (user_id, sort_order, category, title, organizer, activity_date, description)
                   VALUES (?,?,?,?,?,?,?)""",
                (uid, i,
                 award_cats[i].strip() if i < len(award_cats) else "",
                 title,
                 award_orgs[i].strip() if i < len(award_orgs) else "",
                 award_dates[i].strip() if i < len(award_dates) else "",
                 award_descs[i].strip() if i < len(award_descs) else ""),
            )

        # 포트폴리오
        conn.execute("DELETE FROM portfolio_links WHERE user_id=?", (uid,))
        port_types = form.getlist("port_type")
        port_urls = form.getlist("port_url")
        port_descs = form.getlist("port_desc")
        for i in range(len(port_urls)):
            url = port_urls[i].strip()
            if not url:
                continue
            conn.execute(
                """INSERT INTO portfolio_links
                   (user_id, sort_order, link_type, url, description)
                   VALUES (?,?,?,?,?)""",
                (uid, i,
                 port_types[i].strip() if i < len(port_types) else "",
                 url,
                 port_descs[i].strip() if i < len(port_descs) else ""),
            )

        # 자기소개서
        conn.execute("DELETE FROM self_intro_items WHERE user_id=?", (uid,))
        intro_titles = form.getlist("intro_title")
        intro_contents = form.getlist("intro_content")
        for i in range(len(intro_titles)):
            title = intro_titles[i].strip()
            content = intro_contents[i].strip() if i < len(intro_contents) else ""
            if not title and not content:
                continue
            conn.execute(
                """INSERT INTO self_intro_items
                   (user_id, sort_order, title, content)
                   VALUES (?,?,?,?)""",
                (uid, i, title, content[:1000]),
            )

        # seeker_profiles
        params = (
            disability_type_id, severity, gender, birth_year, region_id,
            education_level, career_years,
            desired_job, work_pref,
            mobility_type, commute_max_minutes,
            communication_pref, assistive_tech,
            daily_work_hours, preferred_time, rest_frequency,
            accommodation_needs, resume_path, consent_sensitive, disability_visibility,
        )
        if existing:
            conn.execute("""UPDATE seeker_profiles SET
                disability_type_id=?, severity=?, gender=?, birth_year=?, region_id=?,
                education_level=?, career_years=?,
                desired_job=?, work_pref=?,
                mobility_type=?, commute_max_minutes=?,
                communication_pref=?, assistive_tech=?,
                daily_work_hours=?, preferred_time=?, rest_frequency=?,
                accommodation_needs=?, resume_path=?, consent_sensitive=?, disability_visibility=?,
                consented_at=datetime('now','localtime'),
                updated_at=datetime('now','localtime')
                WHERE user_id=?""",
                params + (uid,))
        else:
            conn.execute("""INSERT INTO seeker_profiles
                (user_id, disability_type_id, severity, gender, birth_year, region_id,
                 education_level, career_years,
                 desired_job, work_pref,
                 mobility_type, commute_max_minutes,
                 communication_pref, assistive_tech,
                 daily_work_hours, preferred_time, rest_frequency,
                 accommodation_needs, resume_path, consent_sensitive, disability_visibility, consented_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))""",
                (uid,) + params)

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
            "SELECT job_id FROM bookmarks WHERE user_id=?", (user["user_id"],)
        ).fetchall()
        for row in bookmark_rows:
            bookmarked_ids.add(row["job_id"])
        seeker_profile = conn.execute(
            "SELECT accommodation_needs FROM seeker_profiles WHERE user_id=?",
            (user["user_id"],),
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
            "user_name": user["user_name"], "user_role": "seeker",
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
            (user["user_id"],),
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
            (job_id, user["user_id"]),
        ).fetchone()
        company = conn.execute(
            "SELECT company_name FROM companies WHERE id=?", (job["company_id"],)
        ).fetchone()
        company_name = company["company_name"] if company else ""
        disability_type = conn.execute(
            "SELECT name FROM disability_types WHERE id=?", (profile["disability_type_id"],)
        ).fetchone()
        disability_name = disability_type["name"] if disability_type else ""
        resume_filename = ""
        if profile["resume_path"]:
            resume_filename = os.path.basename(profile["resume_path"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/apply_form.html", context={
            "request": request, "page_title": "지원서 작성",
            "user_name": user["user_name"], "user_role": "seeker",
            "job": job,
            "already_applied": already_applied is not None,
            "profile": profile,
            "company_name": company_name,
            "disability_name": disability_name,
            "resume_filename": resume_filename,
        }
    )


@router.post("/apply/{job_id}")
async def apply_submit(
    request: Request,
    job_id: int,
    cover_letter: str = Form(""),
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
            cur = conn.execute(
                """INSERT INTO candidacies (job_id, seeker_user_id, source, status, cover_letter)
                   VALUES (?,?,'direct','pending',?)""",
                (job_id, user["user_id"], cover_letter),
            )
            conn.execute(
                """INSERT INTO status_history (candidacy_id, from_status, to_status, actor_id, comment)
                   VALUES (?,?,?,?,?)""",
                (cur.lastrowid, "", "pending", user["user_id"], "직접 지원"),
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
            log.exception("지원서 제출 실패: job_id=%s user_id=%s", job_id, user["user_id"])
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
            (user["user_id"],),
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
            "user_name": user["user_name"], "user_role": "seeker",
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
            (candidacy_id, user["user_id"]),
        ).fetchone()
        if cand and cand["status"] not in ("hired", "rejected", "withdrawn"):
            conn.execute(
                "UPDATE candidacies SET status='withdrawn', updated_at=datetime('now','localtime') WHERE id=?",
                (candidacy_id,),
            )
            conn.execute(
                """INSERT INTO status_history (candidacy_id, from_status, to_status, actor_id, comment)
                   VALUES (?,?,?,?,?)""",
                (candidacy_id, cand["status"], "withdrawn", user["user_id"], "지원 취소"),
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
            """SELECT c.id, c.created_at,
                      jp.title AS job_title, jp.employment_type,
                      r.sido AS region_sido, r.sigungu AS region_sigungu,
                      co.company_name
               FROM candidacies c
               JOIN job_postings jp ON c.job_id = jp.id
               JOIN companies co ON jp.company_id = co.id
               LEFT JOIN regions r ON jp.region_id = r.id
               WHERE c.seeker_user_id = ?
                 AND c.source = 'operator_matched'
                 AND c.match_stage = 'proposed'
               ORDER BY c.created_at DESC""",
            (user["user_id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/proposals.html", context={
            "request": request, "page_title": "매칭 제안",
            "user_name": user["user_name"], "user_role": "seeker",
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
            (candidacy_id, user["user_id"]),
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
                    (candidacy_id, cand["status"], cand["status"], user["user_id"]),
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
                    (candidacy_id, cand["status"], user["user_id"]),
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
            (user["user_id"], job_id),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM bookmarks WHERE id=?", (existing["id"],))
            bookmarked = False
        else:
            conn.execute(
                "INSERT INTO bookmarks (user_id, job_id) VALUES (?,?)",
                (user["user_id"], job_id),
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
            (user["user_id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/bookmarks.html", context={
            "request": request, "page_title": "저장한 공고",
            "user_name": user["user_name"], "user_role": "seeker",
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
            (user["user_id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/recent.html", context={
            "request": request, "page_title": "최근 본 공고",
            "user_name": user["user_name"], "user_role": "seeker",
            "jobs": jobs,
        }
    )


@router.get("/companies/{company_id}", response_class=HTMLResponse)
async def company_detail(request: Request, company_id: int):
    user = require_role(request, "seeker", "operator")
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
            "user_name": user["user_name"], "user_role": "seeker",
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
            (user["user_id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/profile_views.html", context={
            "request": request, "page_title": "프로필 열람 현황",
            "user_name": user["user_name"], "user_role": "seeker",
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
        profile = conn.execute(
            "SELECT accommodation_needs FROM seeker_profiles WHERE user_id=?",
            (user["user_id"],),
        ).fetchone()
        seeker_needs = json.loads(profile["accommodation_needs"]) if profile and profile["accommodation_needs"] else []
        accommodations_provided = json.loads(job["accommodations_provided"]) if job and job["accommodations_provided"] else []
        preferred_disability = json.loads(job["preferred_disability"]) if job and job["preferred_disability"] else []
        is_bookmarked = conn.execute(
            "SELECT 1 FROM bookmarks WHERE user_id=? AND job_id=?",
            (user["user_id"], job_id),
        ).fetchone() is not None
        if job is not None:
            conn.execute(
                "INSERT INTO recent_views (user_id, job_id, viewed_at) VALUES (?,?,datetime('now','localtime')) "
                "ON CONFLICT(user_id, job_id) DO UPDATE SET viewed_at=datetime('now','localtime')",
                (user["user_id"], job_id),
            )
            conn.commit()
    finally:
        conn.close()
    if job is None:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    return templates.TemplateResponse(
        request=request, name="seeker/job_detail.html", context={
            "request": request, "page_title": job["title"],
            "user_name": user["user_name"], "user_role": "seeker",
            "job": job,
            "accommodations_provided": accommodations_provided,
            "preferred_disability": preferred_disability,
            "seeker_needs": seeker_needs,
            "is_bookmarked": is_bookmarked,
        }
    )
