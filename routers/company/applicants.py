from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.candidacy import apply_transition, get_next_statuses, get_pipeline_display, get_stage_labels, get_stage_color_map

router = APIRouter(prefix="/company")


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
        pipeline_stages = get_pipeline_display(conn, company["id"])
        stage_labels = get_stage_labels(conn, company["id"])
        stage_colors = get_stage_color_map(conn, company["id"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/applicants.html", context={
            "request": request, "page_title": f"지원자 목록 - {job['title']}",
            "user_name": user["user_name"], "user_role": "company",
            "job": job,
            "applicants": applicants,
            "status_labels": stage_labels,
            "pipeline_stages": pipeline_stages,
            "stage_colors": stage_colors,
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
        next_statuses = get_next_statuses(conn, company["id"], current_status)
        stage_labels = get_stage_labels(conn, company["id"])
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
            "status_labels": stage_labels,
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
