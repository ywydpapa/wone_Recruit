from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import STATUS_LABELS, MATCH_STAGE_LABELS
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification
from core.matching import match_score
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
            my_seekers = conn.execute(
                "SELECT u.id, u.name FROM users u "
                "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
                "WHERE ma.manager_user_id = ? ORDER BY u.name",
                (user["id"],),
            ).fetchall()
            return templates.TemplateResponse(
                request=request, name="manager/matching.html", context={
                    "request": request, "page_title": "매칭 - 공고 선택",
                    "user_name": user["name"], "user_role": "manager",
                    "open_jobs": open_jobs, "job": None, "candidates": None,
                    "my_seekers": my_seekers,
                }
            )

        job = conn.execute(
            """SELECT jp.*, c.company_name, c.accessibility_facilities, c.remote_ok, c.flexible_ok,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM job_postings jp
               JOIN companies c ON jp.company_id = c.id
               LEFT JOIN regions r ON jp.region_id = r.id
               WHERE jp.id = ?""",
            (job_id,),
        ).fetchone()

        # 내 담당 구직자 중 미지원자
        candidates = conn.execute(
            """SELECT u.id, u.name, sp.work_pref,
                      sp.severity, dt.name AS disability_name,
                      sp.desired_job, sp.daily_work_hours, sp.accommodation_needs,
                      sp.target_categories, sp.assistive_tech,
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
        if job["category_id"]:
            job_category = conn.execute(
                "SELECT * FROM job_categories WHERE id=?", (job["category_id"],)
            ).fetchone()

        scores = {c["id"]: match_score(conn, c, job, job_category) for c in candidates}
        candidates = sorted(candidates, key=lambda c: scores[c["id"]]["score"], reverse=True)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="manager/matching.html", context={
            "request": request, "page_title": "매칭 - 후보자 선택",
            "user_name": user["name"], "user_role": "manager",
            "open_jobs": None, "job": job, "job_id": job_id,
            "candidates": candidates, "scores": scores,
        }
    )


@router.get("/matching/seeker/{seeker_id}", response_class=HTMLResponse)
async def mgr_matching_seeker(request: Request, seeker_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        assigned = conn.execute(
            "SELECT 1 FROM manager_assignments WHERE manager_user_id=? AND seeker_user_id=?",
            (user["id"], seeker_id),
        ).fetchone()
        if not assigned:
            raise HTTPException(status_code=404)

        seeker = conn.execute(
            """SELECT u.id, u.name, sp.severity, dt.name AS disability_name,
                      sp.desired_job, sp.daily_work_hours, sp.accommodation_needs,
                      sp.target_categories, sp.assistive_tech, sp.consent_sensitive,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM users u
               JOIN seeker_profiles sp ON u.id = sp.user_id
               LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id
               LEFT JOIN regions r ON sp.region_id = r.id
               WHERE u.id = ?""",
            (seeker_id,),
        ).fetchone()

        jobs = None
        scores = None
        if seeker["consent_sensitive"]:
            jobs = conn.execute(
                """SELECT jp.*, c.company_name, c.accessibility_facilities, c.remote_ok, c.flexible_ok,
                          r.sido AS region_sido, r.sigungu AS region_sigungu
                   FROM job_postings jp
                   JOIN companies c ON jp.company_id = c.id
                   LEFT JOIN regions r ON jp.region_id = r.id
                   WHERE jp.status = 'open'
                     AND jp.id NOT IN (
                         SELECT job_id FROM candidacies WHERE seeker_user_id = ?
                     )""",
                (seeker_id,),
            ).fetchall()
            cats = {row["id"]: row for row in conn.execute("SELECT * FROM job_categories").fetchall()}
            scores = {j["id"]: match_score(conn, seeker, j, cats.get(j["category_id"])) for j in jobs}
            jobs = sorted(jobs, key=lambda j: scores[j["id"]]["score"], reverse=True)[:30]
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="manager/matching_seeker.html", context={
            "request": request, "page_title": "매칭 - 추천 공고",
            "user_name": user["name"], "user_role": "manager",
            "seeker": seeker, "jobs": jobs, "scores": scores,
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
        create_notification(conn, seeker_user_id, f"[{job_title}] 매니저가 매칭을 제안했습니다.", "/proposals", kind="proposal")
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
    hl: Optional[int] = Query(None),
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
        seekers = conn.execute(
            "SELECT u.id, u.name FROM users u "
            "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
            "WHERE ma.manager_user_id = ? ORDER BY u.name",
            (user["id"],),
        ).fetchall()
        confirmed_cnt = conn.execute(
            """SELECT COUNT(*) FROM candidacies c
               JOIN manager_assignments ma ON ma.seeker_user_id = c.seeker_user_id
               WHERE ma.manager_user_id = ? AND c.match_stage = 'seeker_confirmed'""",
            (user["id"],),
        ).fetchone()[0]
    finally:
        conn.close()
    qs_parts = []
    if seeker_id:
        qs_parts.append(f"seeker_id={seeker_id}")
    if status:
        qs_parts.append(f"status={status}")
    if match_stage:
        qs_parts.append(f"match_stage={match_stage}")
    return templates.TemplateResponse(
        request=request, name="manager/candidacies.html", context={
            "request": request, "page_title": "지원 현황",
            "user_name": user["name"], "user_role": "manager",
            "candidacies": candidacies,
            "seekers": seekers,
            "selected_seeker": seeker_id or "",
            "selected_status": status or "",
            "match_stage": match_stage or "",
            "hl": hl,
            "confirmed_cnt": confirmed_cnt,
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
                    kind="apply",
                )
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/mgr/candidacies", status_code=303)
