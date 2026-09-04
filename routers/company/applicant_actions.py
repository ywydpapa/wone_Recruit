from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.candidacy import get_pipeline_display, get_stage_labels, get_stage_color_map

router = APIRouter(prefix="/company")


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


@router.get("/applicants", response_class=HTMLResponse)
async def applicants_all(request: Request, status: str = "", job_id: str = ""):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)

        where = ["jp.company_id=?"]
        params = [company["id"]]
        where.append("(c.source='direct' OR c.match_stage='submitted')")
        if status:
            where.append("c.status=?")
            params.append(status)
        if job_id:
            where.append("c.job_id=?")
            params.append(int(job_id))

        applicants = conn.execute(
            f"""SELECT c.id, c.job_id, c.status, c.source, c.created_at,
                       u.name AS seeker_name, jp.title AS job_title
                FROM candidacies c
                JOIN users u ON c.seeker_user_id=u.id
                JOIN job_postings jp ON c.job_id=jp.id
                WHERE {' AND '.join(where)}
                ORDER BY c.created_at DESC""",
            params,
        ).fetchall()

        jobs = conn.execute(
            "SELECT id, title FROM job_postings WHERE company_id=? ORDER BY created_at DESC",
            (company["id"],),
        ).fetchall()

        pipeline_stages = get_pipeline_display(conn, company["id"])
        stage_labels = get_stage_labels(conn, company["id"])
        stage_colors = get_stage_color_map(conn, company["id"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/applicants_all.html", context={
            "request": request, "page_title": "지원자 관리",
            "user_name": user["user_name"], "user_role": "company",
            "applicants": applicants, "jobs": jobs,
            "status_labels": stage_labels,
            "pipeline_stages": pipeline_stages,
            "stage_colors": stage_colors,
            "cur_status": status, "cur_job_id": job_id,
        }
    )
