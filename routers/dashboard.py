from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.constants import STATUS_LABELS
from core.db import get_sqlite
from core.deps import check_login, get_current_user, templates
from core.dashboard_data import get_seeker_dashboard, get_company_dashboard, get_operator_dashboard

router = APIRouter()

IV_TYPE_LABELS = {"onsite": "대면", "video": "화상", "phone": "전화"}
JOB_STAT_BADGE = {"open": ("모집중", "bg-success"), "closed": ("마감", "bg-secondary")}


def next_step(d):
    if not d["has_profile"]:
        return {"text": "프로필을 작성하면 매니저가 맞는 일자리를 찾아드릴 수 있어요.", "href": "/profile", "label": "프로필 작성"}
    if d["proposals"]:
        return {"text": f"매니저가 제안한 공고 {d['proposals']}건이 답변을 기다리고 있어요.", "href": "/proposals", "label": "제안 확인"}
    if d["upcoming_schedule"]:
        ev = d["upcoming_schedule"][0]
        mm, dd = ev["date_display"].split("-")
        return {"text": f"{int(mm)}월 {int(dd)}일 {ev['time_display']} {ev['title']} 일정이 있어요.", "href": "/schedule", "label": "일정 보기"}
    if not d["manager"]:
        return {"text": "상담을 신청하면 담당 매니저가 배정되어 구직을 함께 준비해요.", "href": "/consult/new", "label": "상담 신청"}
    if d["profile_completeness"]["percent"] < 80:
        return {"text": f"프로필이 {d['profile_completeness']['percent']}% 작성되었어요. 나머지를 채우면 추천이 더 정확해져요.", "href": "/profile", "label": "이어서 작성"}
    return {"text": "새로 올라온 공고를 살펴보고 마음에 드는 곳에 지원해 보세요.", "href": "/jobs", "label": "공고 보기"}


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
            ctx["apps"] = [{**dict(a), "status_label": STATUS_LABELS[a["status"]]} for a in data["apps"]]
            ctx["next_step"] = next_step(data)
            tpl = "top/seeker_dash.html"
        elif role == "company":
            data = get_company_dashboard(conn, user["id"])
            ctx.update(data)
            ctx["upcoming_interviews"] = [
                {**dict(iv), "initial": iv["seeker_name"][:1],
                 "type_label": IV_TYPE_LABELS.get(iv["interview_type"], iv["interview_type"])}
                for iv in data.get("upcoming_interviews", [])
            ]
            ctx["recent_apps"] = [
                {**dict(a), "initial": a["seeker_name"][:1]} for a in data.get("recent_apps", [])
            ]
            ctx["job_stats"] = [
                {**dict(js), "status_label": JOB_STAT_BADGE.get(js["status"], (js["status"], "bg-secondary"))[0],
                 "status_badge": JOB_STAT_BADGE.get(js["status"], (js["status"], "bg-secondary"))[1]}
                for js in data.get("job_stats", [])
            ]
            tpl = "top/company_dash.html"
        elif role == "manager":
            conn.close()
            return RedirectResponse(url="/mgr/", status_code=303)
        elif role == "operator":
            data = get_operator_dashboard(conn)
            ctx.update(data)
            ctx["status_labels"] = STATUS_LABELS
            tpl = "top/operator_dash.html"
        else:
            tpl = "top/seeker_dash.html"
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name=tpl, context=ctx)
