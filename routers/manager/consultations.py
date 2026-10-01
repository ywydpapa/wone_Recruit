import calendar
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.notifications import create_notification

router = APIRouter()

SESSION_TYPE_LABELS = {
    'initial_assessment': '초기 평가',
    'career_counseling': '진로 상담',
    'interview_prep': '면접 준비',
    'followup_call': '후속 통화',
    'company_visit': '기업 방문',
    'other': '기타',
}

METHOD_LABELS = {
    'in_person': '대면',
    'phone': '전화',
    'video': '화상',
}

CONSULT_STATUS_LABELS = {
    'scheduled': '예정',
    'completed': '완료',
    'cancelled': '취소',
    'no_show': '노쇼',
}

_DOW = ["월", "화", "수", "목", "금", "토", "일"]


@router.get("/consultations", response_class=HTMLResponse)
async def mgr_consultations(
    request: Request,
    status: str = Query(None),
    seeker_id: int = Query(None),
    year: int = Query(None),
    month: int = Query(None),
):
    user = require_role(request, "manager")
    now = datetime.now()
    today = date.today()
    cal_year = year or today.year
    cal_month = month or today.month

    range_start = (today - timedelta(days=90)).isoformat()
    range_end = (today + timedelta(days=90)).isoformat()

    conn = get_sqlite()
    try:
        sql = """SELECT cs.*, u.name AS seeker_name
                 FROM consultation_sessions cs
                 JOIN users u ON cs.seeker_user_id = u.id
                 WHERE cs.manager_user_id = ?
                   AND cs.scheduled_at IS NOT NULL
                   AND date(replace(cs.scheduled_at, 'T', ' ')) BETWEEN ? AND ?"""
        params = [user["id"], range_start, range_end]
        if status:
            sql += " AND cs.status = ?"
            params.append(status)
        if seeker_id:
            sql += " AND cs.seeker_user_id = ?"
            params.append(seeker_id)
        sql += " ORDER BY cs.scheduled_at"
        rows = conn.execute(sql, params).fetchall()

        # 상태별 건수는 필터와 무관하게 집계함
        count_sql = """SELECT status, COUNT(*) as cnt
                       FROM consultation_sessions
                       WHERE manager_user_id = ?
                         AND scheduled_at IS NOT NULL
                         AND date(replace(scheduled_at, 'T', ' ')) BETWEEN ? AND ?"""
        count_params = [user["id"], range_start, range_end]
        if seeker_id:
            count_sql += " AND seeker_user_id = ?"
            count_params.append(seeker_id)
        count_sql += " GROUP BY status"
        status_counts = {r["status"]: r["cnt"] for r in conn.execute(count_sql, count_params).fetchall()}

        seekers = conn.execute(
            "SELECT u.id, u.name FROM users u "
            "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
            "WHERE ma.manager_user_id = ? ORDER BY u.name",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()

    today_str = today.isoformat()
    tomorrow_str = (today + timedelta(days=1)).isoformat()
    event_dates = set()
    grouped = {}

    for r in rows:
        r = dict(r)
        norm = (r["scheduled_at"] or "").replace("T", " ")
        ds = norm[:10]
        r["time_str"] = norm[11:16]
        event_dates.add(ds)
        grouped.setdefault(ds, []).append(r)

    date_groups = []
    for ds in sorted(grouped):
        try:
            d = date.fromisoformat(ds)
            if ds == today_str:
                label = "오늘"
            elif ds == tomorrow_str:
                label = "내일"
            else:
                label = f"{d.month}/{d.day} ({_DOW[d.weekday()]})"
        except ValueError:
            label = ds
        date_groups.append({"label": label, "is_today": ds == today_str, "date_str": ds, "events": grouped[ds]})

    cal_obj = calendar.Calendar(firstweekday=6)
    weeks = []
    for wk in cal_obj.monthdatescalendar(cal_year, cal_month):
        weeks.append([{
            "date": d, "in_month": d.month == cal_month,
            "is_today": d == today, "has_event": d.isoformat() in event_dates,
        } for d in wk])

    if cal_month == 1:
        prev_y, prev_m = cal_year - 1, 12
    else:
        prev_y, prev_m = cal_year, cal_month - 1
    if cal_month == 12:
        next_y, next_m = cal_year + 1, 1
    else:
        next_y, next_m = cal_year, cal_month + 1

    qs_parts = []
    if status:
        qs_parts.append(f"status={status}")
    if seeker_id:
        qs_parts.append(f"seeker_id={seeker_id}")
    base_qs = "&".join(qs_parts)

    return templates.TemplateResponse(
        request=request, name="manager/consultations.html", context={
            "request": request, "page_title": "상담 관리",
            "user_name": user["name"], "user_role": "manager",
            "date_groups": date_groups,
            "status_counts": status_counts,
            "seekers": seekers,
            "selected_status": status or "",
            "selected_seeker": seeker_id or "",
            "type_labels": SESSION_TYPE_LABELS,
            "method_labels": METHOD_LABELS,
            "status_labels": CONSULT_STATUS_LABELS,
            "base_qs": base_qs,
            "cal_year": cal_year, "cal_month": cal_month, "weeks": weeks,
            "prev_year": prev_y, "prev_month": prev_m,
            "next_year": next_y, "next_month": next_m,
            "today_year": now.year, "today_month": now.month,
        }
    )


@router.get("/consultations/new", response_class=HTMLResponse)
async def mgr_consultation_new(request: Request, seeker_id: int = Query(None), request_id: int = Query(None)):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        if seeker_id:
            seeker = conn.execute("SELECT * FROM users WHERE id=? AND role='seeker'", (seeker_id,)).fetchone()
        else:
            seeker = None
        seekers = conn.execute(
            "SELECT u.id, u.name FROM users u "
            "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
            "WHERE ma.manager_user_id = ? ORDER BY u.name",
            (user["id"],),
        ).fetchall()
        preselect_method = ""
        if request_id:
            req = conn.execute(
                "SELECT cr.method FROM consult_requests cr "
                "JOIN manager_assignments ma ON ma.seeker_user_id = cr.seeker_user_id "
                "WHERE cr.id=? AND ma.manager_user_id=?",
                (request_id, user["id"]),
            ).fetchone()
            if not req:
                raise HTTPException(status_code=404)
            if req["method"] in METHOD_LABELS:
                preselect_method = req["method"]
    finally:
        conn.close()
    if seeker_id and not seeker:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request=request, name="manager/consultation_form.html", context={
            "request": request, "page_title": "상담 일정 등록",
            "user_name": user["name"], "user_role": "manager",
            "seeker": seeker, "consultation": None,
            "seekers": seekers,
            "preselect_seeker_id": seeker_id or 0,
            "request_id": request_id or 0,
            "preselect_method": preselect_method,
            "session_types": SESSION_TYPE_LABELS,
            "method_labels": METHOD_LABELS,
        }
    )


@router.post("/consultations")
async def mgr_consultation_create(
    request: Request,
    seeker_id: int = Form(...),
    session_type: str = Form("other"),
    scheduled_at: str = Form(""),
    method: str = Form("in_person"),
    location: str = Form(""),
    notes: str = Form(""),
    request_id: int = Form(0),
):
    user = require_role(request, "manager")
    sched = scheduled_at.strip() or None
    status = "scheduled" if sched else "completed"
    conn = get_sqlite()
    try:
        cur = conn.execute(
            "INSERT INTO consultation_sessions "
            "(seeker_user_id, manager_user_id, session_type, scheduled_at, method, location, status, notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (seeker_id, user["id"], session_type, sched, method, location.strip(), status, notes.strip()),
        )
        session_id = cur.lastrowid
        if request_id:
            req = conn.execute(
                "SELECT cr.id FROM consult_requests cr "
                "JOIN manager_assignments ma ON ma.seeker_user_id = cr.seeker_user_id "
                "WHERE cr.id=? AND ma.manager_user_id=?",
                (request_id, user["id"]),
            ).fetchone()
            if req:
                conn.execute(
                    "UPDATE consult_requests SET status='scheduled', session_id=?, manager_user_id=?, "
                    "handled_at=datetime('now','localtime') WHERE id=?",
                    (session_id, user["id"], request_id),
                )
                create_notification(conn, seeker_id, "상담 일정이 확정되었습니다", "/consult", kind="consult")
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/seekers/{seeker_id}", status_code=303)


@router.get("/consultations/{session_id}/edit", response_class=HTMLResponse)
async def mgr_consultation_edit(request: Request, session_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT * FROM consultation_sessions WHERE id=?", (session_id,)).fetchone()
        if not row or row["manager_user_id"] != user["id"]:
            raise HTTPException(status_code=404)
        seeker = conn.execute("SELECT * FROM users WHERE id=?", (row["seeker_user_id"],)).fetchone()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="manager/consultation_form.html", context={
            "request": request, "page_title": "상담 수정",
            "user_name": user["name"], "user_role": "manager",
            "seeker": seeker, "consultation": row,
            "seekers": [],
            "preselect_seeker_id": 0,
            "request_id": 0,
            "preselect_method": "",
            "session_types": SESSION_TYPE_LABELS,
            "method_labels": METHOD_LABELS,
        }
    )


@router.post("/consultations/{session_id}")
async def mgr_consultation_update(
    request: Request,
    session_id: int,
    seeker_id: int = Form(...),
    session_type: str = Form("other"),
    scheduled_at: str = Form(""),
    method: str = Form("in_person"),
    location: str = Form(""),
    notes: str = Form(""),
):
    user = require_role(request, "manager")
    sched = scheduled_at.strip() or None
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE consultation_sessions "
            "SET session_type=?, scheduled_at=?, method=?, location=?, notes=? "
            "WHERE id=? AND manager_user_id=?",
            (session_type, sched, method, location.strip(), notes.strip(), session_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/seekers/{seeker_id}", status_code=303)


@router.post("/consultations/{session_id}/complete")
async def mgr_consultation_complete(request: Request, session_id: int):
    user = require_role(request, "manager")
    form = await request.form()
    seeker_id = form.get("seeker_id")
    conn = get_sqlite()
    try:
        cur = conn.execute(
            "UPDATE consultation_sessions SET status='completed' WHERE id=? AND manager_user_id=?",
            (session_id, user["id"]),
        )
        if cur.rowcount:
            conn.execute("UPDATE consult_requests SET status='done' WHERE session_id=?", (session_id,))
        conn.commit()
    finally:
        conn.close()
    redirect = form.get("redirect", f"/mgr/seekers/{seeker_id}")
    return RedirectResponse(url=redirect, status_code=303)


@router.post("/consultations/{session_id}/cancel")
async def mgr_consultation_cancel(request: Request, session_id: int):
    user = require_role(request, "manager")
    form = await request.form()
    seeker_id = form.get("seeker_id")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE consultation_sessions SET status='cancelled' WHERE id=? AND manager_user_id=?",
            (session_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    redirect = form.get("redirect", f"/mgr/seekers/{seeker_id}")
    return RedirectResponse(url=redirect, status_code=303)


@router.post("/consultations/{session_id}/no_show")
async def mgr_consultation_no_show(request: Request, session_id: int):
    user = require_role(request, "manager")
    form = await request.form()
    seeker_id = form.get("seeker_id")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE consultation_sessions SET status='no_show' WHERE id=? AND manager_user_id=?",
            (session_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    redirect = form.get("redirect", f"/mgr/seekers/{seeker_id}")
    return RedirectResponse(url=redirect, status_code=303)


@router.post("/consultations/{session_id}/delete")
async def mgr_consultation_delete(request: Request, session_id: int):
    user = require_role(request, "manager")
    form = await request.form()
    seeker_id = form.get("seeker_id")
    conn = get_sqlite()
    try:
        conn.execute(
            "DELETE FROM consultation_sessions WHERE id=? AND manager_user_id=?",
            (session_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    redirect = form.get("redirect", f"/mgr/seekers/{seeker_id}")
    return RedirectResponse(url=redirect, status_code=303)
