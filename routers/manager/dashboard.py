from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from routers.manager.consultations import SESSION_TYPE_LABELS, METHOD_LABELS

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def mgr_dashboard(request: Request):
    user = require_role(request, "manager")
    uid = user["id"]
    conn = get_sqlite()
    try:
        # 긴급 액션 카드
        today_followups = conn.execute(
            """SELECT COUNT(*) FROM placement_followups pf
               JOIN placements p ON pf.placement_id = p.id
               WHERE p.seeker_user_id IN (SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id=?)
                 AND pf.status='pending' AND pf.due_date = date('now','localtime')""",
            (uid,),
        ).fetchone()[0]

        overdue_followups = conn.execute(
            """SELECT COUNT(*) FROM placement_followups pf
               JOIN placements p ON pf.placement_id = p.id
               WHERE p.seeker_user_id IN (SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id=?)
                 AND pf.status='overdue'""",
            (uid,),
        ).fetchone()[0]

        pending_matches = conn.execute(
            """SELECT COUNT(*) FROM candidacies
               WHERE seeker_user_id IN (SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id=?)
                 AND match_stage='proposed' AND status='pending'""",
            (uid,),
        ).fetchone()[0]

        unassigned_count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='seeker' AND id NOT IN (SELECT seeker_user_id FROM manager_assignments)"
        ).fetchone()[0]

        # 파이프라인
        my_seekers_sql = "SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id=?"
        total_caseload = conn.execute(
            f"SELECT COUNT(*) FROM ({my_seekers_sql})", (uid,)
        ).fetchone()[0]

        in_counseling = conn.execute(
            """SELECT COUNT(DISTINCT ma.seeker_user_id)
               FROM manager_assignments ma
               LEFT JOIN candidacies c ON c.seeker_user_id = ma.seeker_user_id
               WHERE ma.manager_user_id=? AND c.id IS NULL""",
            (uid,),
        ).fetchone()[0]

        in_matching = conn.execute(
            """SELECT COUNT(DISTINCT c.seeker_user_id)
               FROM candidacies c
               WHERE c.seeker_user_id IN (SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id=?)
                 AND c.status IN ('pending', 'reviewing', 'shortlisted')
                 AND c.seeker_user_id NOT IN (SELECT seeker_user_id FROM placements)""",
            (uid,),
        ).fetchone()[0]

        in_interview = conn.execute(
            """SELECT COUNT(DISTINCT c.seeker_user_id)
               FROM candidacies c
               WHERE c.seeker_user_id IN (SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id=?)
                 AND c.status = 'interview'
                 AND c.seeker_user_id NOT IN (SELECT seeker_user_id FROM placements)""",
            (uid,),
        ).fetchone()[0]

        placed_active = conn.execute(
            """SELECT COUNT(*) FROM placements
               WHERE seeker_user_id IN (SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id=?)
                 AND (status IS NULL OR status='active')""",
            (uid,),
        ).fetchone()[0]

        placed_settled = conn.execute(
            """SELECT COUNT(*) FROM placements
               WHERE seeker_user_id IN (SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id=?)
                 AND status='settled'""",
            (uid,),
        ).fetchone()[0]

        # 예정 상담
        upcoming_sessions = conn.execute(
            """SELECT cs.*, u.name AS seeker_name
               FROM consultation_sessions cs
               JOIN users u ON cs.seeker_user_id = u.id
               WHERE cs.manager_user_id=? AND cs.status='scheduled'
               ORDER BY cs.scheduled_at ASC LIMIT 5""",
            (uid,),
        ).fetchall()
        # 최근 완료 상담
        recent_sessions = conn.execute(
            """SELECT cs.*, u.name AS seeker_name
               FROM consultation_sessions cs
               JOIN users u ON cs.seeker_user_id = u.id
               WHERE cs.manager_user_id=? AND cs.status != 'scheduled'
               ORDER BY cs.created_at DESC LIMIT 5""",
            (uid,),
        ).fetchall()
    finally:
        conn.close()

    pipeline = [
        ("상담중", in_counseling, "counseling"),
        ("매칭중", in_matching, "matching"),
        ("면접", in_interview, "interview"),
        ("배치", placed_active, "placed"),
        ("정착", placed_settled, "settled"),
    ]

    return templates.TemplateResponse(
        request=request, name="manager/dashboard.html", context={
            "request": request, "page_title": "매니저 대시보드",
            "user_name": user["name"], "user_role": "manager",
            "today_followups": today_followups,
            "overdue_followups": overdue_followups,
            "pending_matches": pending_matches,
            "unassigned_count": unassigned_count,
            "total_caseload": total_caseload,
            "pipeline": pipeline,
            "upcoming_sessions": upcoming_sessions,
            "recent_sessions": recent_sessions,
            "type_labels": SESSION_TYPE_LABELS,
            "method_labels": METHOD_LABELS,
        }
    )
