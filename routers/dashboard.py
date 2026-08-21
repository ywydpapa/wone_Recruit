from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import check_login, get_current_user, templates
from core.dashboard_data import get_seeker_dashboard, get_company_dashboard, get_operator_dashboard

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = get_current_user(request)
    role = user["user_role"]
    conn = get_sqlite()
    try:
        ctx = {"request": request, "page_title": "대시보드",
               "user_name": user["user_name"], "user_role": role}
        if role == "seeker":
            ctx.update(get_seeker_dashboard(conn, user["user_id"]))
            tpl = "top/seeker_dash.html"
        elif role == "company":
            ctx.update(get_company_dashboard(conn, user["user_id"]))
            tpl = "top/company_dash.html"
        elif role == "operator":
            ctx.update(get_operator_dashboard(conn))
            tpl = "top/operator_dash.html"
        else:
            tpl = "top/seeker_dash.html"
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name=tpl, context=ctx)
