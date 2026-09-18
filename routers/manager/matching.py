import json
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import STATUS_LABELS, MATCH_STAGE_LABELS
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification
from core.matching import build_capability_profile, calc_category_fit
from core.logger import log

router = APIRouter()


@router.get("/matching", response_class=HTMLResponse)
async def mgr_matching(request: Request, job_id: int = None):
    user = require_role(request, "manager")
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
                request=request, name="manager/matching.html", context={
                    "request": request, "page_title": "매칭 - 공고 선택",
                    "user_name": user["name"], "user_role": "manager",
                    "open_jobs": open_jobs, "job": None, "candidates": None,
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

        # 내 담당 구직자 중 미지원자
        candidates = conn.execute(
            """SELECT u.id, u.name, sp.work_pref,
                      sp.severity, dt.name AS disability_name,
                      sp.desired_job, sp.daily_work_hours, sp.accommodation_needs,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM users u
               JOIN manager_assignments ma ON ma.seeker_user_id = u.id
               JOIN seeker_profiles sp ON u.id = sp.user_id
               LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id
               LEFT JOIN regions r ON sp.region_id = r.id
               WHERE ma.manager_user_id = ?
                 AND sp.consent_sensitive = 1
                 AND u.id NOT IN (
                     SELECT seeker_user_id FROM candidacies WHERE job_id = ?
                 )
               ORDER BY u.id""",
            (user["id"], job_id),
        ).fetchall()

        job_category = None
        if job and job["category_id"]:
            job_category = conn.execute(
                "SELECT * FROM job_categories WHERE id=?", (job["category_id"],)
            ).fetchone()

        compatibility = {}
        for c in candidates:
            needs = json.loads(c["accommodation_needs"]) if c["accommodation_needs"] else []
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
                "accommodation": len(set(needs) & set(job_accommodations)) if needs and job_accommodations else 0,
                "accommodation_total": len(needs) if needs else 0,
                "fit_score": fit,
                "fit_label": fit_label,
            }
        candidates = sorted(candidates, key=lambda c: compatibility[c["id"]]["fit_score"], reverse=True)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="manager/matching.html", context={
            "request": request, "page_title": "매칭 - 후보자 선택",
            "user_name": user["name"], "user_role": "manager",
            "open_jobs": None, "job": job, "job_id": job_id,
            "candidates": candidates, "compatibility": compatibility,
        }
    )


@router.post("/matching/propose")
async def mgr_propose(
    request: Request,
    job_id: int = Form(...),
    seeker_user_id: int = Form(...),
):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        cur = conn.execute(
            """INSERT INTO candidacies
               (job_id, seeker_user_id, source, status, match_stage, assigned_manager_id)
               VALUES (?, ?, 'operator_matched', 'pending', 'proposed', ?)""",
            (job_id, seeker_user_id, user["id"]),
        )
        conn.execute(
            """INSERT INTO status_history
               (candidacy_id, from_status, to_status, actor_id, comment)
               VALUES (?, '', 'pending', ?, '매니저 매칭 제안')""",
            (cur.lastrowid, user["id"]),
        )
        job = conn.execute("SELECT title FROM job_postings WHERE id=?", (job_id,)).fetchone()
        job_title = job["title"] if job else "공고"
        create_notification(conn, seeker_user_id, f"[{job_title}] 매니저가 매칭을 제안했습니다.", "/proposals")
        conn.commit()
    except Exception:
        log.exception("매칭 제안 실패: job_id=%s seeker=%s", job_id, seeker_user_id)
        conn.rollback()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/matching?job_id={job_id}", status_code=303)


@router.get("/pending-matches", response_class=HTMLResponse)
async def mgr_pending_matches(request: Request):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        rows = conn.execute(
            """SELECT c.id, c.seeker_user_id, c.job_id, c.match_stage, c.created_at,
                      u.name AS seeker_name, jp.title AS job_title,
                      co.company_name, jp.company_id
               FROM candidacies c
               JOIN users u ON c.seeker_user_id = u.id
               JOIN job_postings jp ON c.job_id = jp.id
               JOIN companies co ON jp.company_id = co.id
               WHERE c.seeker_user_id IN (
                   SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id = ?
               ) AND c.match_stage = 'proposed' AND c.status = 'pending'
               ORDER BY c.created_at DESC""",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="manager/pending_matches.html", context={
            "request": request, "page_title": "대기중 매칭",
            "user_name": user["name"], "user_role": "manager",
            "rows": rows,
        }
    )


@router.get("/candidacies", response_class=HTMLResponse)
async def mgr_candidacies(
    request: Request,
    seeker_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    match_stage: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        sql = """SELECT c.id, c.seeker_user_id, c.job_id, c.status, c.source, c.match_stage, c.created_at,
                      jp.title AS job_title, jp.company_id, co.company_name, u.name AS seeker_name
               FROM candidacies c
               JOIN job_postings jp ON c.job_id = jp.id
               JOIN companies co ON jp.company_id = co.id
               JOIN users u ON c.seeker_user_id = u.id
               WHERE c.seeker_user_id IN (
                   SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id = ?
               )"""
        params = [user["id"]]
        if seeker_id:
            sql += " AND c.seeker_user_id = ?"
            params.append(seeker_id)
        if status:
            sql += " AND c.status = ?"
            params.append(status)
        if match_stage:
            sql += " AND c.match_stage = ?"
            params.append(match_stage)
        sql += " ORDER BY c.created_at DESC"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        candidacies = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
        # 필터 드롭다운용 담당 구직자 목록
        seekers = conn.execute(
            "SELECT u.id, u.name FROM users u "
            "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
            "WHERE ma.manager_user_id = ? ORDER BY u.name",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    qs_parts = []
    if seeker_id:
        qs_parts.append(f"seeker_id={seeker_id}")
    if status:
        qs_parts.append(f"status={status}")
    return templates.TemplateResponse(
        request=request, name="manager/candidacies.html", context={
            "request": request, "page_title": "지원 현황",
            "user_name": user["name"], "user_role": "manager",
            "candidacies": candidacies,
            "seekers": seekers,
            "selected_seeker": seeker_id or "",
            "selected_status": status or "",
            "status_labels": STATUS_LABELS,
            "match_stage_labels": MATCH_STAGE_LABELS,
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.post("/matching/{candidacy_id}/submit")
async def mgr_submit(request: Request, candidacy_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        cand = conn.execute("SELECT * FROM candidacies WHERE id=?", (candidacy_id,)).fetchone()
        if cand and cand["match_stage"] == "seeker_confirmed":
            conn.execute(
                "UPDATE candidacies SET match_stage='submitted', updated_at=datetime('now','localtime') WHERE id=?",
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
    return RedirectResponse(url="/mgr/candidacies", status_code=303)
