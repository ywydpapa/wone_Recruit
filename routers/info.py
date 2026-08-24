from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from core.db import get_sqlite
from core.deps import check_login, require_role, templates
from core.notifications import get_unread_count

router = APIRouter()


@router.get("/api/regions")
async def api_regions(sido: str = Query("")):
    conn = get_sqlite()
    try:
        if sido:
            rows = conn.execute(
                "SELECT id, sigungu FROM regions WHERE sido=? ORDER BY sigungu",
                (sido,),
            ).fetchall()
            return JSONResponse([{"id": r["id"], "sigungu": r["sigungu"]} for r in rows])
        else:
            rows = conn.execute(
                "SELECT DISTINCT sido FROM regions ORDER BY sido"
            ).fetchall()
            return JSONResponse([r["sido"] for r in rows])
    finally:
        conn.close()


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse(
        request=request, name="info/policy.html", context={
            "request": request, "page_title": "개인정보처리방침",
            "policy_type": "privacy",
        }
    )


@router.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return templates.TemplateResponse(
        request=request, name="info/policy.html", context={
            "request": request, "page_title": "이용약관",
            "policy_type": "terms",
        }
    )


@router.get("/api/notifications/count")
async def notification_count(request: Request):
    if not check_login(request):
        return {"count": 0}
    user_id = request.session.get("user_id")
    return {"count": get_unread_count(user_id)}


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    user = require_role(request, "seeker", "company", "operator")
    conn = get_sqlite()
    try:
        notifications = conn.execute(
            "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 100",
            (user["user_id"],),
        ).fetchall()
        conn.execute(
            "UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0",
            (user["user_id"],),
        )
        conn.commit()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="info/notifications.html", context={
            "request": request, "page_title": "알림",
            "user_name": user["user_name"], "user_role": user["user_role"],
            "notifications": notifications,
        }
    )
