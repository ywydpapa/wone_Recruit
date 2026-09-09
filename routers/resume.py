import json
import os
from datetime import datetime

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.upload import save_upload
from core.resume_completeness import calc_completeness
from core.constants import (
    EDUCATION_LEVELS_DETAIL, GRADUATION_STATUS, GPA_SCALES,
    CAREER_EMPLOYMENT_TYPES, LANGUAGE_LIST, LANGUAGE_LEVELS,
    AWARD_CATEGORIES, PORTFOLIO_LINK_TYPES,
    MOBILITY_TYPES, COMMUTE_OPTIONS,
    DAILY_HOURS_OPTIONS, PREFERRED_TIME_OPTIONS,
    REST_FREQUENCY_OPTIONS, ACCOMMODATION_OPTIONS,
)

router = APIRouter()


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


def build_resume_snapshot(conn, resume_id):
    resume = conn.execute("SELECT * FROM resumes WHERE id=?", (resume_id,)).fetchone()
    if not resume:
        return '{}'
    data = dict(resume)
    data['educations'] = [dict(r) for r in conn.execute(
        "SELECT * FROM resume_educations WHERE resume_id=? ORDER BY sort_order", (resume_id,)
    ).fetchall()]
    data['careers'] = [dict(r) for r in conn.execute(
        "SELECT * FROM resume_careers WHERE resume_id=? ORDER BY sort_order", (resume_id,)
    ).fetchall()]
    data['certifications'] = [dict(r) for r in conn.execute(
        "SELECT * FROM resume_certifications WHERE resume_id=? ORDER BY sort_order", (resume_id,)
    ).fetchall()]
    data['languages'] = [dict(r) for r in conn.execute(
        "SELECT * FROM resume_languages WHERE resume_id=? ORDER BY sort_order", (resume_id,)
    ).fetchall()]
    data['awards'] = [dict(r) for r in conn.execute(
        "SELECT * FROM resume_awards WHERE resume_id=? ORDER BY sort_order", (resume_id,)
    ).fetchall()]
    data['portfolios'] = [dict(r) for r in conn.execute(
        "SELECT * FROM resume_portfolios WHERE resume_id=? ORDER BY sort_order", (resume_id,)
    ).fetchall()]
    data['intros'] = [dict(r) for r in conn.execute(
        "SELECT * FROM resume_intros WHERE resume_id=? ORDER BY sort_order", (resume_id,)
    ).fetchall()]
    return json.dumps(data, ensure_ascii=False, default=str)


@router.get("/resumes", response_class=HTMLResponse)
async def resume_list(request: Request):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        resumes = conn.execute(
            "SELECT * FROM resumes WHERE user_id=? ORDER BY is_default DESC, updated_at DESC",
            (user["id"],),
        ).fetchall()
        label_map = {'edu': '학력', 'career': '경력', 'cert': '자격증', 'lang': '어학', 'award': '수상', 'portfolio': '포트폴리오'}
        item_counts = {}
        item_summaries = {}
        for r in resumes:
            rid = r["id"]
            item_counts[rid] = {
                "edu": conn.execute(
                    "SELECT COUNT(*) FROM resume_educations WHERE resume_id=?", (rid,)
                ).fetchone()[0],
                "career": conn.execute(
                    "SELECT COUNT(*) FROM resume_careers WHERE resume_id=?", (rid,)
                ).fetchone()[0],
                "cert": conn.execute(
                    "SELECT COUNT(*) FROM resume_certifications WHERE resume_id=?", (rid,)
                ).fetchone()[0],
                "lang": conn.execute(
                    "SELECT COUNT(*) FROM resume_languages WHERE resume_id=?", (rid,)
                ).fetchone()[0],
                "award": conn.execute(
                    "SELECT COUNT(*) FROM resume_awards WHERE resume_id=?", (rid,)
                ).fetchone()[0],
                "portfolio": conn.execute(
                    "SELECT COUNT(*) FROM resume_portfolios WHERE resume_id=?", (rid,)
                ).fetchone()[0],
                "intro": conn.execute(
                    "SELECT COUNT(*) FROM resume_intros WHERE resume_id=?", (rid,)
                ).fetchone()[0],
            }
            counts = item_counts[rid]
            parts = [f"{label_map[k]} {v}" for k, v in counts.items() if k in label_map and v > 0]
            item_summaries[rid] = ' | '.join(parts)
        updated_dates = {r["id"]: (r["updated_at"][:10] if r["updated_at"] else '-') for r in resumes}
        completeness_map = {r["id"]: calc_completeness(conn, r["id"]) for r in resumes}
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/resume_list.html", context={
            "request": request, "page_title": "내 이력서",
            "user_name": user["name"], "user_role": "seeker",
            "user": user,
            "resumes": resumes,
            "item_counts": item_counts,
            "item_summaries": item_summaries,
            "updated_dates": updated_dates,
            "completeness_map": completeness_map,
        }
    )


@router.post("/resumes/new")
async def resume_new(
    request: Request,
    name: str = Form(""),
    copy_from: int = Form(None),
):
    user = require_role(request, "seeker")
    uid = user["id"]
    conn = get_sqlite()
    try:
        existing_count = conn.execute(
            "SELECT COUNT(*) FROM resumes WHERE user_id=?", (uid,)
        ).fetchone()[0]
        resume_name = name.strip() if name.strip() else f"이력서 {existing_count + 1}"
        is_default = 1 if existing_count == 0 else 0

        cur = conn.execute(
            """INSERT INTO resumes (user_id, name, is_default, created_at, updated_at)
               VALUES (?,?,?,datetime('now','localtime'),datetime('now','localtime'))""",
            (uid, resume_name, is_default),
        )
        new_id = cur.lastrowid

        if copy_from:
            src = conn.execute(
                "SELECT * FROM resumes WHERE id=? AND user_id=?", (copy_from, uid)
            ).fetchone()
            if src:
                fields = [
                    "desired_job", "work_pref", "mobility_type", "commute_max_minutes",
                    "daily_work_hours", "preferred_time", "rest_frequency",
                    "accommodation_needs", "experience_summary",
                ]
                update_parts = ", ".join(f"{f}=?" for f in fields)
                vals = [src[f] for f in fields]
                conn.execute(
                    f"UPDATE resumes SET {update_parts} WHERE id=?",
                    vals + [new_id],
                )

                for edu in conn.execute(
                    "SELECT * FROM resume_educations WHERE resume_id=? ORDER BY sort_order", (copy_from,)
                ).fetchall():
                    conn.execute(
                        """INSERT INTO resume_educations
                           (resume_id, sort_order, education_level, school_name, major,
                            start_date, end_date, graduation_status, gpa, gpa_scale, is_transfer)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (new_id, edu["sort_order"], edu["education_level"], edu["school_name"],
                         edu["major"], edu["start_date"], edu["end_date"], edu["graduation_status"],
                         edu["gpa"], edu["gpa_scale"], edu["is_transfer"]),
                    )

                for car in conn.execute(
                    "SELECT * FROM resume_careers WHERE resume_id=? ORDER BY sort_order", (copy_from,)
                ).fetchall():
                    conn.execute(
                        """INSERT INTO resume_careers
                           (resume_id, sort_order, company_name, department, position,
                            start_date, end_date, is_current, employment_type, description)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (new_id, car["sort_order"], car["company_name"], car["department"],
                         car["position"], car["start_date"], car["end_date"],
                         car["is_current"], car["employment_type"], car["description"]),
                    )

                for cert in conn.execute(
                    "SELECT * FROM resume_certifications WHERE resume_id=? ORDER BY sort_order", (copy_from,)
                ).fetchall():
                    conn.execute(
                        """INSERT INTO resume_certifications
                           (resume_id, sort_order, cert_name, cert_date, issuing_org)
                           VALUES (?,?,?,?,?)""",
                        (new_id, cert["sort_order"], cert["cert_name"], cert["cert_date"], cert["issuing_org"]),
                    )

                for lang in conn.execute(
                    "SELECT * FROM resume_languages WHERE resume_id=? ORDER BY sort_order", (copy_from,)
                ).fetchall():
                    conn.execute(
                        """INSERT INTO resume_languages
                           (resume_id, sort_order, language, test_name, score, level, test_date)
                           VALUES (?,?,?,?,?,?,?)""",
                        (new_id, lang["sort_order"], lang["language"], lang["test_name"],
                         lang["score"], lang["level"], lang["test_date"]),
                    )

                for award in conn.execute(
                    "SELECT * FROM resume_awards WHERE resume_id=? ORDER BY sort_order", (copy_from,)
                ).fetchall():
                    conn.execute(
                        """INSERT INTO resume_awards
                           (resume_id, sort_order, category, title, organizer, activity_date, description)
                           VALUES (?,?,?,?,?,?,?)""",
                        (new_id, award["sort_order"], award["category"], award["title"],
                         award["organizer"], award["activity_date"], award["description"]),
                    )

                for port in conn.execute(
                    "SELECT * FROM resume_portfolios WHERE resume_id=? ORDER BY sort_order", (copy_from,)
                ).fetchall():
                    conn.execute(
                        """INSERT INTO resume_portfolios
                           (resume_id, sort_order, link_type, url, description)
                           VALUES (?,?,?,?,?)""",
                        (new_id, port["sort_order"], port["link_type"], port["url"], port["description"]),
                    )

                for intro in conn.execute(
                    "SELECT * FROM resume_intros WHERE resume_id=? ORDER BY sort_order", (copy_from,)
                ).fetchall():
                    conn.execute(
                        """INSERT INTO resume_intros
                           (resume_id, sort_order, title, content, char_limit)
                           VALUES (?,?,?,?,?)""",
                        (new_id, intro["sort_order"], intro["title"], intro["content"], intro["char_limit"]),
                    )

        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/resumes/{new_id}/edit", status_code=303)


@router.get("/resumes/{resume_id}/edit", response_class=HTMLResponse)
async def resume_edit(request: Request, resume_id: int, success: str = "", error: str = ""):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        resume = conn.execute(
            "SELECT * FROM resumes WHERE id=? AND user_id=?",
            (resume_id, user["id"]),
        ).fetchone()
        if resume is None:
            return RedirectResponse(url="/resumes", status_code=303)
        education_list = conn.execute(
            "SELECT * FROM resume_educations WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        career_list = conn.execute(
            "SELECT * FROM resume_careers WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        certifications = conn.execute(
            "SELECT * FROM resume_certifications WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        language_list = conn.execute(
            "SELECT * FROM resume_languages WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        awards_list = conn.execute(
            "SELECT * FROM resume_awards WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        portfolio_list = conn.execute(
            "SELECT * FROM resume_portfolios WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        intro_list = conn.execute(
            "SELECT * FROM resume_intros WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        intro_presets = conn.execute(
            "SELECT * FROM self_intro_presets WHERE is_active=1 ORDER BY sort_order"
        ).fetchall()
        accommodation_needs = json.loads(resume["accommodation_needs"]) if resume["accommodation_needs"] else []
        profile = conn.execute(
            "SELECT * FROM seeker_profiles WHERE user_id=?", (user["id"],)
        ).fetchone()
        selected_sido = ""
        if profile and profile["region_id"]:
            region_row = conn.execute("SELECT sido FROM regions WHERE id=?", (profile["region_id"],)).fetchone()
            if region_row:
                selected_sido = region_row["sido"]
        birth_display = str(profile["birth_year"]) if profile and profile["birth_year"] else ""
        resume_filename = resume["resume_path"].split('/')[-1] if resume["resume_path"] else ""
        resume_photo_url = resume["photo_path"] or ""
        photo_btn_label = "변경" if resume_photo_url else "사진 등록"
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/resume_form.html", context={
            "request": request, "page_title": resume["name"],
            "user_name": user["name"], "user_role": "seeker",
            "user": user,
            "profile": profile,
            "selected_sido": selected_sido,
            "birth_display": birth_display,
            "resume": resume,
            "resume_filename": resume_filename,
            "resume_photo_url": resume_photo_url,
            "photo_btn_label": photo_btn_label,
            "education_list": education_list,
            "career_list": career_list,
            "certifications": certifications,
            "language_list": language_list,
            "awards_list": awards_list,
            "portfolio_list": portfolio_list,
            "intro_list": intro_list,
            "intro_presets": intro_presets,
            "accommodation_needs": accommodation_needs,
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
            "daily_hours_options": DAILY_HOURS_OPTIONS,
            "preferred_time_options": PREFERRED_TIME_OPTIONS,
            "rest_frequency_options": REST_FREQUENCY_OPTIONS,
            "accommodation_options": ACCOMMODATION_OPTIONS,
            "success": success, "error": error,
        }
    )


@router.get("/resumes/{resume_id}", response_class=HTMLResponse)
async def resume_detail(request: Request, resume_id: int):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        resume = conn.execute(
            "SELECT * FROM resumes WHERE id=? AND user_id=?",
            (resume_id, user["id"]),
        ).fetchone()
        if resume is None:
            return RedirectResponse(url="/resumes", status_code=303)
        profile = conn.execute(
            "SELECT * FROM seeker_profiles WHERE user_id=?", (user["id"],)
        ).fetchone()
        education_list = conn.execute(
            "SELECT * FROM resume_educations WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        career_list = conn.execute(
            "SELECT * FROM resume_careers WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        certifications = conn.execute(
            "SELECT * FROM resume_certifications WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        language_list = conn.execute(
            "SELECT * FROM resume_languages WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        awards_list = conn.execute(
            "SELECT * FROM resume_awards WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        portfolio_list = conn.execute(
            "SELECT * FROM resume_portfolios WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        intro_list = conn.execute(
            "SELECT * FROM resume_intros WHERE resume_id=? ORDER BY sort_order", (resume_id,)
        ).fetchall()
        accommodation_needs = json.loads(resume["accommodation_needs"]) if resume["accommodation_needs"] else []
        birth_display = str(profile["birth_year"]) if profile and profile["birth_year"] else ""
        region_name = ""
        if profile and profile["region_id"]:
            rr = conn.execute("SELECT sido, sigungu FROM regions WHERE id=?", (profile["region_id"],)).fetchone()
            if rr:
                region_name = rr["sido"] + " " + rr["sigungu"]
        photo_url = resume["photo_path"] if resume["photo_path"] else ""
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="seeker/resume_detail.html", context={
            "request": request, "page_title": resume["name"],
            "user_name": user["name"], "user_role": "seeker",
            "user": user,
            "profile": profile,
            "resume": resume,
            "birth_display": birth_display,
            "region_name": region_name,
            "photo_url": photo_url,
            "education_list": education_list,
            "career_list": career_list,
            "certifications": certifications,
            "language_list": language_list,
            "awards_list": awards_list,
            "portfolio_list": portfolio_list,
            "intro_list": intro_list,
            "accommodation_needs": accommodation_needs,
        }
    )


@router.post("/resumes/{resume_id}")
async def resume_save(request: Request, resume_id: int, resume_file: UploadFile = File(None)):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        existing = conn.execute(
            "SELECT * FROM resumes WHERE id=? AND user_id=?",
            (resume_id, user["id"]),
        ).fetchone()
        if existing is None:
            return RedirectResponse(url="/resumes", status_code=303)

        form = await request.form()
        name = form.get("name", "").strip() or existing["name"]
        desired_job = form.get("desired_job", "")
        work_pref = form.get("work_pref", "무관")
        mobility_type = form.get("mobility_type", "")
        commute_max_minutes = int(form.get("commute_max_minutes") or 0) or None
        daily_work_hours = int(form.get("daily_work_hours") or 8)
        preferred_time = form.get("preferred_time", "풀타임")
        rest_frequency = form.get("rest_frequency", "불필요")
        experience_summary = form.get("experience_summary", "")
        accommodation_needs = json.dumps(form.getlist("accommodation_needs"), ensure_ascii=False)

        resume_path = existing["resume_path"] or ""
        if resume_file and resume_file.filename:
            resume_path = await save_upload(
                resume_file, "resumes", user["id"],
                ["application/pdf"], 10 * 1024 * 1024,
            )

        # 증명사진
        photo_path = existing["photo_path"] or ""
        if form.get("photo_delete") == "1":
            photo_path = ""
        photo_file = form.get("photo")
        if photo_file and hasattr(photo_file, 'filename') and photo_file.filename:
            uploaded = await save_upload(
                photo_file, "resume_photos", user["id"],
                ["image/jpeg", "image/png", "image/webp"], 5 * 1024 * 1024,
            )
            if uploaded:
                photo_path = uploaded

        # 기본정보 (프로필 반영)
        phone = form.get("phone", "").strip()
        region_id = int(form.get("region_id") or 0) or None
        if phone:
            conn.execute("UPDATE users SET phone=? WHERE id=?", (phone, user["id"]))
        if region_id:
            conn.execute(
                "UPDATE seeker_profiles SET region_id=?, updated_at=datetime('now','localtime') WHERE user_id=?",
                (region_id, user["id"]),
            )

        # 학력
        conn.execute("DELETE FROM resume_educations WHERE resume_id=?", (resume_id,))
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
            }
            edu_rows.append(row)
            conn.execute(
                """INSERT INTO resume_educations
                   (resume_id, sort_order, education_level, school_name, major,
                    start_date, end_date, graduation_status, gpa, gpa_scale)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (resume_id, i, row["education_level"], row["school_name"], row["major"],
                 row["start_date"], row["end_date"], row["graduation_status"],
                 row["gpa"], row["gpa_scale"]),
            )

        # 경력
        conn.execute("DELETE FROM resume_careers WHERE resume_id=?", (resume_id,))
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
                """INSERT INTO resume_careers
                   (resume_id, sort_order, company_name, department, position,
                    start_date, end_date, is_current, employment_type, description)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (resume_id, i, company,
                 car_depts[i].strip() if i < len(car_depts) else "",
                 car_positions[i].strip() if i < len(car_positions) else "",
                 row["start_date"], row["end_date"], is_current,
                 car_emp_types[i].strip() if i < len(car_emp_types) else "",
                 car_descs[i].strip() if i < len(car_descs) else ""),
            )

        education_level = _calc_education_level(edu_rows)
        career_years = _calc_career_years(career_rows)

        # 자격증
        conn.execute("DELETE FROM resume_certifications WHERE resume_id=?", (resume_id,))
        cert_names = form.getlist("cert_name")
        cert_dates = form.getlist("cert_date")
        cert_orgs = form.getlist("cert_org")
        for i in range(len(cert_names)):
            name_val = cert_names[i].strip()
            if not name_val:
                continue
            conn.execute(
                """INSERT INTO resume_certifications
                   (resume_id, sort_order, cert_name, cert_date, issuing_org)
                   VALUES (?,?,?,?,?)""",
                (resume_id, i, name_val,
                 cert_dates[i].strip() if i < len(cert_dates) else "",
                 cert_orgs[i].strip() if i < len(cert_orgs) else ""),
            )

        # 어학
        conn.execute("DELETE FROM resume_languages WHERE resume_id=?", (resume_id,))
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
                """INSERT INTO resume_languages
                   (resume_id, sort_order, language, test_name, score, level, test_date)
                   VALUES (?,?,?,?,?,?,?)""",
                (resume_id, i, language, test,
                 lang_scores[i].strip() if i < len(lang_scores) else "",
                 lang_levels[i].strip() if i < len(lang_levels) else "",
                 lang_dates[i].strip() if i < len(lang_dates) else ""),
            )

        # 수상/활동
        conn.execute("DELETE FROM resume_awards WHERE resume_id=?", (resume_id,))
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
                """INSERT INTO resume_awards
                   (resume_id, sort_order, category, title, organizer, activity_date, description)
                   VALUES (?,?,?,?,?,?,?)""",
                (resume_id, i,
                 award_cats[i].strip() if i < len(award_cats) else "",
                 title,
                 award_orgs[i].strip() if i < len(award_orgs) else "",
                 award_dates[i].strip() if i < len(award_dates) else "",
                 award_descs[i].strip() if i < len(award_descs) else ""),
            )

        # 포트폴리오
        conn.execute("DELETE FROM resume_portfolios WHERE resume_id=?", (resume_id,))
        port_types = form.getlist("port_type")
        port_urls = form.getlist("port_url")
        port_descs = form.getlist("port_desc")
        for i in range(len(port_urls)):
            url = port_urls[i].strip()
            if not url:
                continue
            conn.execute(
                """INSERT INTO resume_portfolios
                   (resume_id, sort_order, link_type, url, description)
                   VALUES (?,?,?,?,?)""",
                (resume_id, i,
                 port_types[i].strip() if i < len(port_types) else "",
                 url,
                 port_descs[i].strip() if i < len(port_descs) else ""),
            )

        # 자기소개서
        conn.execute("DELETE FROM resume_intros WHERE resume_id=?", (resume_id,))
        intro_titles = form.getlist("intro_title")
        intro_contents = form.getlist("intro_content")
        intro_char_limits = form.getlist("intro_char_limit")
        for i in range(len(intro_titles)):
            title = intro_titles[i].strip()
            content = intro_contents[i].strip() if i < len(intro_contents) else ""
            if not title and not content:
                continue
            char_limit = int(intro_char_limits[i]) if i < len(intro_char_limits) and intro_char_limits[i].strip().isdigit() else None
            conn.execute(
                """INSERT INTO resume_intros
                   (resume_id, sort_order, title, content, char_limit)
                   VALUES (?,?,?,?,?)""",
                (resume_id, i, title, content, char_limit),
            )

        conn.execute(
            """UPDATE resumes SET
               name=?, desired_job=?, work_pref=?, mobility_type=?, commute_max_minutes=?,
               daily_work_hours=?, preferred_time=?, rest_frequency=?,
               accommodation_needs=?, experience_summary=?, resume_path=?, photo_path=?,
               updated_at=datetime('now','localtime')
               WHERE id=?""",
            (name, desired_job, work_pref, mobility_type, commute_max_minutes,
             daily_work_hours, preferred_time, rest_frequency,
             accommodation_needs, experience_summary, resume_path, photo_path,
             resume_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/resumes/{resume_id}/edit?success=1", status_code=303)


@router.delete("/resumes/{resume_id}")
async def resume_delete(request: Request, resume_id: int):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        resume = conn.execute(
            "SELECT * FROM resumes WHERE id=? AND user_id=?",
            (resume_id, user["id"]),
        ).fetchone()
        if resume is None:
            return JSONResponse({"redirect": "/resumes"})
        if resume["is_default"]:
            return JSONResponse({"error": "기본 이력서는 삭제할 수 없습니다"}, status_code=400)
        conn.execute("DELETE FROM resumes WHERE id=?", (resume_id,))
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"redirect": "/resumes"})


@router.post("/resumes/{resume_id}/default")
async def resume_set_default(request: Request, resume_id: int):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        resume = conn.execute(
            "SELECT id FROM resumes WHERE id=? AND user_id=?",
            (resume_id, user["id"]),
        ).fetchone()
        if resume is None:
            return RedirectResponse(url="/resumes", status_code=303)
        conn.execute(
            "UPDATE resumes SET is_default=0 WHERE user_id=?", (user["id"],)
        )
        conn.execute(
            "UPDATE resumes SET is_default=1 WHERE id=?", (resume_id,)
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/resumes", status_code=303)
