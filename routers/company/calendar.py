import calendar
from datetime import date, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates

router = APIRouter(prefix="/company")

_IV_TYPE = {"onsite": "대면", "video": "화상", "phone": "전화"}
_DOW = ["월", "화", "수", "목", "금", "토", "일"]


@router.get("/calendar", response_class=HTMLResponse)
async def interview_calendar(request: Request, year: int = 0, month: int = 0):
    user = require_role(request, "company")
    today = date.today()
    cal_year = year or today.year
    cal_month = month or today.month

    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        if company["approval_status"] != "approved":
            return RedirectResponse(url="/?error=not_approved", status_code=303)

        range_start = (today - timedelta(days=90)).isoformat()
        range_end = (today + timedelta(days=90)).isoformat()

        rows = conn.execute(
            """SELECT s.id, s.interview_date, s.interview_time, s.interview_type,
                      s.location, s.memo, s.candidacy_id, c.job_id, c.seeker_user_id,
                      u.name AS seeker_name, jp.title AS job_title
               FROM interview_schedules s
               JOIN candidacies c ON s.candidacy_id = c.id
               JOIN job_postings jp ON c.job_id = jp.id
               JOIN users u ON c.seeker_user_id = u.id
               WHERE jp.company_id = ?
                 AND s.interview_date BETWEEN ? AND ?
               ORDER BY s.interview_date, s.interview_time""",
            (company["id"], range_start, range_end),
        ).fetchall()
    finally:
        conn.close()

    event_dates = set()
    grouped = {}
    for r in rows:
        ds = r["interview_date"]
        event_dates.add(ds)
        grouped.setdefault(ds, []).append(dict(r))

    today_str = today.isoformat()
    tomorrow_str = (today + timedelta(days=1)).isoformat()

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
        date_groups.append({"label": label, "is_today": ds == today_str, "events": grouped[ds]})

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

    return templates.TemplateResponse(
        request=request, name="company/calendar.html", context={
            "request": request, "page_title": "내 일정",
            "user_name": user["name"], "user_role": "company",
            "date_groups": date_groups,
            "cal_year": cal_year, "cal_month": cal_month, "weeks": weeks,
            "prev_year": prev_y, "prev_month": prev_m,
            "next_year": next_y, "next_month": next_m,
            "today_year": today.year, "today_month": today.month,
            "type_labels": _IV_TYPE,
        }
    )
