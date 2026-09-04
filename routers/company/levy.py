from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.levy import calc_levy

router = APIRouter(prefix="/company")


@router.get("/levy", response_class=HTMLResponse)
async def company_levy(request: Request):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        rates_rows = conn.execute("SELECT rate_type, amount FROM levy_rates WHERE year=2026").fetchall()
        rates = {r["rate_type"]: r["amount"] for r in rates_rows}
    finally:
        conn.close()

    result = calc_levy(company["employee_count"], company["disabled_count"], rates)

    return templates.TemplateResponse(
        request=request, name="company/levy.html", context={
            "request": request, "page_title": "장애인 고용부담금",
            "user_name": user["user_name"], "user_role": "company",
            "company": company, "levy": result,
        }
    )
