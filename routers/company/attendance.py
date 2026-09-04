import calendar
from datetime import date, datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates

router = APIRouter(prefix="/company")

ATTENDANCE_STATUS_LABELS = {
    "normal": "정상",
    "late": "지각",
    "early_leave": "조퇴",
    "absent": "결근",
    "vacation": "휴가",
    "half_day": "반차",
}


def _get_hired_employees(conn, company_id):
    return conn.execute(
        """SELECT DISTINCT u.id AS user_id, u.name AS user_name
           FROM placements p
           JOIN users u ON p.seeker_user_id=u.id
           WHERE p.company_id=?
           ORDER BY u.name""",
        (company_id,),
    ).fetchall()


@router.get("/attendance", response_class=HTMLResponse)
async def attendance_daily(request: Request, date: str = ""):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)

        work_date = date if date else datetime.now().strftime("%Y-%m-%d")
        employees = _get_hired_employees(conn, company["id"])

        records = {}
        rows = conn.execute(
            "SELECT * FROM attendance WHERE company_id=? AND work_date=?",
            (company["id"], work_date),
        ).fetchall()
        for r in rows:
            records[r["employee_user_id"]] = r
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="company/attendance.html", context={
            "request": request, "page_title": "근태관리",
            "user_name": user["user_name"], "user_role": "company",
            "work_date": work_date,
            "employees": employees,
            "records": records,
            "status_labels": ATTENDANCE_STATUS_LABELS,
        }
    )


@router.post("/attendance")
async def attendance_save(request: Request):
    user = require_role(request, "company")
    form = await request.form()
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT id FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        work_date = form.get("work_date", "")
        employee_ids = form.getlist("employee_user_id")
        for eid in employee_ids:
            eid_int = int(eid)
            check_in = form.get(f"check_in_{eid}", "") or None
            check_out = form.get(f"check_out_{eid}", "") or None
            status = form.get(f"status_{eid}", "normal")
            memo = form.get(f"memo_{eid}", "")
            conn.execute(
                """INSERT INTO attendance (company_id, employee_user_id, work_date, check_in, check_out, status, memo)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(company_id, employee_user_id, work_date)
                   DO UPDATE SET check_in=excluded.check_in, check_out=excluded.check_out,
                                 status=excluded.status, memo=excluded.memo,
                                 updated_at=datetime('now','localtime')""",
                (company["id"], eid_int, work_date, check_in, check_out, status, memo),
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/company/attendance?date={work_date}", status_code=303)


@router.get("/attendance/monthly", response_class=HTMLResponse)
async def attendance_monthly(
    request: Request,
    year: int = 0,
    month: int = 0,
):
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

        employees = _get_hired_employees(conn, company["id"])
        days_in_month = calendar.monthrange(year, month)[1]

        date_from = f"{year}-{month:02d}-01"
        date_to = f"{year}-{month:02d}-{days_in_month:02d}"
        rows = conn.execute(
            "SELECT * FROM attendance WHERE company_id=? AND work_date BETWEEN ? AND ?",
            (company["id"], date_from, date_to),
        ).fetchall()

        grid = {}
        for r in rows:
            grid[(r["employee_user_id"], r["work_date"])] = r["status"]

        summaries = {}
        for emp in employees:
            uid = emp["user_id"]
            s = {"work": 0, "late": 0, "absent": 0, "vacation": 0, "half_day": 0, "early_leave": 0}
            for day in range(1, days_in_month + 1):
                d = f"{year}-{month:02d}-{day:02d}"
                st = grid.get((uid, d), "")
                if st == "normal":
                    s["work"] += 1
                elif st in s:
                    s[st] += 1
            summaries[uid] = s
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="company/attendance_monthly.html", context={
            "request": request, "page_title": "월간 근태 현황",
            "user_name": user["user_name"], "user_role": "company",
            "year": year, "month": month,
            "days_in_month": days_in_month,
            "employees": employees,
            "grid": grid,
            "summaries": summaries,
            "status_labels": ATTENDANCE_STATUS_LABELS,
        }
    )
