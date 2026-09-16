import calendar
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.pagination import page_info, PER_PAGE

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


def _build_cal_weeks(year, month, sessions_in_range):
    today = date.today()
    cal = calendar.Calendar(firstweekday=6)  # 일요일 시작
    day_map = {}
    for s in sessions_in_range:
        raw = s['scheduled_at']
        if not raw:
            continue
        ds = raw.replace('T', ' ')[:10]
        day_map.setdefault(ds, []).append({
            'id': s['id'],
            'time': raw.replace('T', ' ')[11:16],
            'seeker_name': s['seeker_name'],
            'status': s['status'],
        })
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        days = []
        for d in week:
            ds = d.isoformat()
            days.append({
                'date': d,
                'in_month': d.month == month,
                'is_today': d == today,
                'sessions': day_map.get(ds, []),
            })
        weeks.append(days)
    return weeks


@router.get("/consultations", response_class=HTMLResponse)
async def mgr_consultations(
    request: Request,
    status: Optional[str] = Query(None),
    seeker_id: Optional[int] = Query(None),
    view: str = Query("list"),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "manager")
    now = datetime.now()
    today_str = date.today().isoformat()

    if view == "calendar":
        if year and month and 1 <= month <= 12 and 1900 <= year <= 2100:
            cal_year, cal_month = year, month
        else:
            cal_year, cal_month = now.year, now.month

        # 달력에 표시할 날짜 범위: monthdatescalendar가 인접 달 날짜 포함할 수 있음
        cal_obj = calendar.Calendar(firstweekday=6)
        all_weeks = cal_obj.monthdatescalendar(cal_year, cal_month)
        range_start = all_weeks[0][0].isoformat()
        range_end = all_weeks[-1][-1].isoformat()

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
            cal_sessions = conn.execute(sql, params).fetchall()
            seekers = conn.execute(
                "SELECT u.id, u.name FROM users u "
                "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
                "WHERE ma.manager_user_id = ? ORDER BY u.name",
                (user["id"],),
            ).fetchall()
        finally:
            conn.close()

        cal_sessions = [dict(r) for r in cal_sessions]
        weeks = _build_cal_weeks(cal_year, cal_month, cal_sessions)

        # 이전/다음 달
        if cal_month == 1:
            prev_year, prev_month = cal_year - 1, 12
        else:
            prev_year, prev_month = cal_year, cal_month - 1
        if cal_month == 12:
            next_year, next_month = cal_year + 1, 1
        else:
            next_year, next_month = cal_year, cal_month + 1

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
                "view": "calendar",
                "cal_year": cal_year, "cal_month": cal_month,
                "weeks": weeks,
                "prev_year": prev_year, "prev_month": prev_month,
                "next_year": next_year, "next_month": next_month,
                "today_year": now.year, "today_month": now.month,
                "seekers": seekers,
                "selected_status": status or "",
                "selected_seeker": seeker_id or "",
                "status_labels": CONSULT_STATUS_LABELS,
                "base_qs": base_qs,
                "sessions": [], "today_sessions": [],
                "pagination": None,
                "type_labels": SESSION_TYPE_LABELS,
                "method_labels": METHOD_LABELS,
            }
        )

    # 리스트 뷰
    conn = get_sqlite()
    try:
        sql = """SELECT cs.*, u.name AS seeker_name
                 FROM consultation_sessions cs
                 JOIN users u ON cs.seeker_user_id = u.id
                 WHERE cs.manager_user_id = ?"""
        params = [user["id"]]
        if status:
            sql += " AND cs.status = ?"
            params.append(status)
        if seeker_id:
            sql += " AND cs.seeker_user_id = ?"
            params.append(seeker_id)
        sql += " ORDER BY COALESCE(cs.scheduled_at, cs.created_at) DESC"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        rows = conn.execute(sql, params).fetchall()
        now_iso = now.isoformat(sep=" ", timespec="seconds")
        sessions = []
        for r in rows:
            r = dict(r)
            r["overdue"] = (
                r["status"] == "scheduled"
                and r["scheduled_at"]
                and r["scheduled_at"].replace("T", " ") < now_iso
            )
            sessions.append(r)
        pagination = page_info(total, page)
        seekers = conn.execute(
            "SELECT u.id, u.name FROM users u "
            "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
            "WHERE ma.manager_user_id = ? ORDER BY u.name",
            (user["id"],),
        ).fetchall()
        today_sessions = conn.execute(
            """SELECT cs.*, u.name AS seeker_name
               FROM consultation_sessions cs
               JOIN users u ON cs.seeker_user_id = u.id
               WHERE cs.manager_user_id = ?
                 AND cs.status = 'scheduled'
                 AND date(replace(cs.scheduled_at, 'T', ' ')) = ?
               ORDER BY cs.scheduled_at""",
            (user["id"], today_str),
        ).fetchall()
    finally:
        conn.close()

    qs_parts = []
    if status:
        qs_parts.append(f"status={status}")
    if seeker_id:
        qs_parts.append(f"seeker_id={seeker_id}")
    return templates.TemplateResponse(
        request=request, name="manager/consultations.html", context={
            "request": request, "page_title": "상담 관리",
            "user_name": user["name"], "user_role": "manager",
            "view": "list",
            "sessions": sessions,
            "today_sessions": today_sessions,
            "seekers": seekers,
            "selected_status": status or "",
            "selected_seeker": seeker_id or "",
            "type_labels": SESSION_TYPE_LABELS,
            "method_labels": METHOD_LABELS,
            "status_labels": CONSULT_STATUS_LABELS,
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/consultations/new", response_class=HTMLResponse)
async def mgr_consultation_new(request: Request, seeker_id: Optional[int] = Query(None)):
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
):
    user = require_role(request, "manager")
    sched = scheduled_at.strip() or None
    consult_status = "scheduled" if sched else "completed"
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO consultation_sessions "
            "(seeker_user_id, manager_user_id, session_type, scheduled_at, method, location, status, notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (seeker_id, user["id"], session_type, sched, method, location.strip(), consult_status, notes.strip()),
        )
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
        conn.execute(
            "UPDATE consultation_sessions SET status='completed' WHERE id=? AND manager_user_id=?",
            (session_id, user["id"]),
        )
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
