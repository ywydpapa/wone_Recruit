from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import STATUS_LABELS, CONSULT_CATEGORIES, CONSULT_REQ_STATUS
from routers.manager.consultations import SESSION_TYPE_LABELS, METHOD_LABELS
from routers.manager.placements import FOLLOWUP_LABELS, PLACEMENT_STATUS

router = APIRouter()

STATUS_BADGE = {
    "pending": "secondary",
    "reviewing": "primary",
    "shortlisted": "info",
    "interview": "warning",
    "offer": "success",
    "hired": "success",
    "rejected": "danger",
    "withdrawn": "light",
}

IV_TYPE_LABELS = {"onsite": "대면", "video": "화상", "phone": "전화"}

PLACEMENT_STATUS_BADGE = {"active": "primary", "settled": "success", "departed": "danger"}

FOLLOWUP_STATUS = {
    "pending": ("예정", "warning"),
    "completed": ("완료", "success"),
    "overdue": ("지연", "danger"),
}


@router.get("/status", response_class=HTMLResponse)
async def status_home(request: Request):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        app_rows = conn.execute(
            """SELECT c.id, c.status, c.created_at, jp.id AS job_id, jp.title, co.company_name
               FROM candidacies c
               JOIN job_postings jp ON c.job_id = jp.id
               JOIN companies co ON jp.company_id = co.id
               WHERE c.seeker_user_id = ? AND c.status NOT IN ('hired','rejected','withdrawn')
               ORDER BY c.created_at DESC""",
            (user["id"],),
        ).fetchall()

        iv_rows = conn.execute(
            """SELECT s.id, s.interview_date, s.interview_time, s.interview_type,
                      s.location, jp.title AS job_title, co.company_name
               FROM interview_schedules s
               JOIN candidacies c ON s.candidacy_id = c.id
               JOIN job_postings jp ON c.job_id = jp.id
               JOIN companies co ON jp.company_id = co.id
               WHERE c.seeker_user_id = ? AND s.interview_date >= date('now','localtime')
               ORDER BY s.interview_date, s.interview_time""",
            (user["id"],),
        ).fetchall()

        proposal_cnt = conn.execute(
            """SELECT COUNT(*) FROM candidacies
               WHERE seeker_user_id = ? AND source = 'operator_matched' AND match_stage = 'proposed'""",
            (user["id"],),
        ).fetchone()[0]

        req_rows = conn.execute(
            """SELECT * FROM consult_requests
               WHERE seeker_user_id = ? AND status IN ('pending','accepted','scheduled')
               ORDER BY created_at DESC""",
            (user["id"],),
        ).fetchall()

        session_rows = conn.execute(
            """SELECT cs.id, cs.scheduled_at, cs.session_type, cs.method
               FROM consultation_sessions cs
               WHERE cs.seeker_user_id = ? AND cs.status = 'scheduled' AND cs.scheduled_at IS NOT NULL
               ORDER BY cs.scheduled_at""",
            (user["id"],),
        ).fetchall()

        place_rows = conn.execute(
            """SELECT p.id, p.start_date, p.end_date, p.status, jp.title AS job_title, co.company_name
               FROM placements p
               JOIN job_postings jp ON p.job_id = jp.id
               JOIN companies co ON p.company_id = co.id
               WHERE p.seeker_user_id = ?
               ORDER BY p.start_date DESC""",
            (user["id"],),
        ).fetchall()

        places = []
        for p in place_rows:
            d = dict(p)
            d["status_label"] = PLACEMENT_STATUS[d["status"]]
            d["status_color"] = PLACEMENT_STATUS_BADGE[d["status"]]
            fup_rows = conn.execute(
                """SELECT id, followup_type, due_date, status, completed_at
                   FROM placement_followups WHERE placement_id = ? ORDER BY due_date""",
                (p["id"],),
            ).fetchall()
            fups = []
            for f in fup_rows:
                fd = dict(f)
                fd["type_label"] = FOLLOWUP_LABELS[fd["followup_type"]]
                fd["status_label"], fd["status_color"] = FOLLOWUP_STATUS[fd["status"]]
                fups.append(fd)
            d["followups"] = fups
            places.append(d)
    finally:
        conn.close()

    apps = []
    for a in app_rows:
        d = dict(a)
        d["status_label"] = STATUS_LABELS[d["status"]]
        d["status_color"] = STATUS_BADGE[d["status"]]
        apps.append(d)

    ivs = []
    for r in iv_rows:
        d = dict(r)
        d["type_label"] = IV_TYPE_LABELS[d["interview_type"]]
        ivs.append(d)

    reqs = []
    for r in req_rows:
        d = dict(r)
        d["category_label"] = CONSULT_CATEGORIES[d["category"]]
        d["status_label"], d["status_color"] = CONSULT_REQ_STATUS[d["status"]]
        reqs.append(d)

    sessions = []
    for r in session_rows:
        d = dict(r)
        d["type_label"] = SESSION_TYPE_LABELS[d["session_type"]]
        d["method_label"] = METHOD_LABELS[d["method"]]
        sessions.append(d)

    return templates.TemplateResponse(
        request=request, name="seeker/status.html", context={
            "request": request, "page_title": "신청현황",
            "user_name": user["name"], "user_role": "seeker",
            "app_count": len(apps), "iv_count": len(ivs),
            "proposal_cnt": proposal_cnt, "consult_cnt": len(reqs),
            "apps": apps[:5], "ivs": ivs[:5],
            "reqs": reqs, "sessions": sessions,
            "places": places,
        }
    )
