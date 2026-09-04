from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.candidacy import get_stage_labels, get_stage_color_map

router = APIRouter(prefix="/company")


@router.get("/recommendations", response_class=HTMLResponse)
async def recommendations(request: Request):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)

        candidates = conn.execute(
            """SELECT c.id, c.job_id, c.status, c.created_at, c.match_stage,
                      u.name AS seeker_name, jp.title AS job_title
               FROM candidacies c
               JOIN users u ON c.seeker_user_id=u.id
               JOIN job_postings jp ON c.job_id=jp.id
               WHERE jp.company_id=? AND c.source='operator_matched' AND c.match_stage='submitted'
               ORDER BY c.created_at DESC""",
            (company["id"],),
        ).fetchall()

        stage_labels = get_stage_labels(conn, company["id"])
        stage_colors = get_stage_color_map(conn, company["id"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/recommendations.html", context={
            "request": request, "page_title": "추천 인재",
            "user_name": user["user_name"], "user_role": "company",
            "candidates": candidates,
            "status_labels": stage_labels,
            "stage_colors": stage_colors,
        }
    )
