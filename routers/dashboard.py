from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.constants import STATUS_LABELS
from core.db import get_sqlite
from core.deps import check_login, get_current_user, templates
from core.dashboard_data import get_seeker_dashboard, get_company_dashboard, get_operator_dashboard

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = get_current_user(request)
    role = user["role"]
    conn = get_sqlite()
    try:
        ctx = {"request": request, "page_title": "대시보드",
               "user_name": user["name"], "user_role": role}
        if role == "seeker":
            data = get_seeker_dashboard(conn, user["id"])
            ctx.update(data)
            ctx["apps"] = [
                {**dict(a), "initial": a["company_name"][:1]} for a in data.get("apps", [])
            ]
            tpl = "top/seeker_dash.html"
        elif role == "company":
            data = get_company_dashboard(conn, user["id"])
            ctx.update(data)
            ctx["upcoming_interviews"] = [
                {**dict(iv), "initial": iv["seeker_name"][:1]} for iv in data.get("upcoming_interviews", [])
            ]
            ctx["recent_apps"] = [
                {**dict(a), "initial": a["seeker_name"][:1]} for a in data.get("recent_apps", [])
            ]
            tpl = "top/company_dash.html"
        elif role == "manager":
            conn.close()
            return RedirectResponse(url="/mgr/", status_code=303)
        elif role == "operator":
            data = get_operator_dashboard(conn)
            ctx.update(data)
            ctx["status_labels"] = STATUS_LABELS
            # 진행중 매칭 합산
            p = data["pipeline"]
            ctx["active_matching"] = sum(p.get(k, 0) for k in ['pending', 'reviewing', 'shortlisted', 'interview', 'offer'])
            # 지원 목록 initial 추가
            ctx["recent_candidacies"] = [
                {**dict(c), "initial": c["seeker_name"][:1]} for c in data.get("recent_candidacies", [])
            ]
            tpl = "top/operator_dash.html"
        else:
            tpl = "top/seeker_dash.html"
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name=tpl, context=ctx)
