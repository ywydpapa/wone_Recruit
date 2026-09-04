import calendar
from datetime import date
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates

router = APIRouter(prefix="/company")


@router.get("/calendar", response_class=HTMLResponse)
async def interview_calendar(request: Request, year: int = 0, month: int = 0):
    user = require_role(request, "company")
    today = date.today()
    if year == 0:
        year = today.year
    if month == 0:
        month = today.month

    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)

        days_in_month = calendar.monthrange(year, month)[1]
        first_weekday = (date(year, month, 1).weekday() + 1) % 7

        date_from = f"{year}-{month:02d}-01"
        date_to = f"{year}-{month:02d}-{days_in_month:02d}"

        interviews = conn.execute(
            """SELECT s.interview_date, s.interview_time, s.interview_type, s.location,
                      u.name AS seeker_name, jp.title AS job_title
               FROM interview_schedules s
               JOIN candidacies c ON s.candidacy_id=c.id
               JOIN job_postings jp ON c.job_id=jp.id
               JOIN users u ON c.seeker_user_id=u.id
               WHERE jp.company_id=? AND s.interview_date BETWEEN ? AND ?
               ORDER BY s.interview_date, s.interview_time""",
            (company["id"], date_from, date_to),
        ).fetchall()

        by_date = {}
        for iv in interviews:
            by_date.setdefault(iv["interview_date"], []).append(iv)

        prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
        next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="company/calendar.html", context={
            "request": request, "page_title": "면접 캘린더",
            "user_name": user["user_name"], "user_role": "company",
            "year": year, "month": month,
            "days_in_month": days_in_month,
            "first_weekday": first_weekday,
            "by_date": by_date,
            "prev_year": prev_year, "prev_month": prev_month,
            "next_year": next_year, "next_month": next_month,
        }
    )
