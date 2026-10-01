import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from core.bizno import check_bizno
from core.db import get_sqlite
from core.deps import check_login, require_role, templates
from core.notifications import KIND_ICONS, KINDS, ROLE_KINDS, get_unread_count
from core.pagination import PER_PAGE, page_info

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


@router.get("/api/bizno/check")
async def api_bizno_check(biz_no: str = Query("")):
    if not biz_no:
        return JSONResponse({"valid": None})
    result = await check_bizno(biz_no)
    return JSONResponse({"valid": result})


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
    user_id = request.session.get("id")
    return {"count": get_unread_count(user_id)}


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request, kind: str = Query(""), page: int = Query(1)):
    user = require_role(request, "seeker", "company", "operator", "manager")
    role_kinds = ROLE_KINDS[user["role"]]
    if kind and kind not in role_kinds:
        kind = ""
    conn = get_sqlite()
    try:
        where = "user_id=?"
        params = [user["id"]]
        if kind:
            where += " AND kind=?"
            params.append(kind)
        total = conn.execute(
            f"SELECT COUNT(*) FROM notifications WHERE {where}", params
        ).fetchone()[0]
        pagination = page_info(total, page)
        rows = conn.execute(
            f"""SELECT * FROM notifications WHERE {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            params + [PER_PAGE, (pagination["page"] - 1) * PER_PAGE],
        ).fetchall()
        # 이번 페이지에 표시된 알림만 읽음 처리함
        ids = [r["id"] for r in rows]
        if ids:
            marks = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE notifications SET is_read=1 WHERE id IN ({marks})", ids
            )
            conn.commit()
        unread = {r["kind"]: r["cnt"] for r in conn.execute(
            "SELECT kind, COUNT(*) AS cnt FROM notifications WHERE user_id=? AND is_read=0 GROUP BY kind",
            (user["id"],),
        ).fetchall()}
    finally:
        conn.close()

    tabs = [{"kind": "", "label": "전체", "count": sum(unread.values())}]
    for k in role_kinds:
        tabs.append({"kind": k, "label": KINDS[k], "count": unread.get(k, 0)})

    return templates.TemplateResponse(
        request=request, name="info/notifications.html", context={
            "request": request, "page_title": "알림",
            "user_name": user["name"], "user_role": user["role"],
            "notifications": rows,
            "kind_icons": KIND_ICONS, "kind_labels": KINDS,
            "tabs": tabs, "selected_kind": kind,
            "pagination": pagination, "base_qs": f"kind={kind}" if kind else "",
        }
    )


@router.post("/notifications/read_all")
async def notifications_read_all(request: Request, kind: str = ""):
    user = require_role(request, "seeker", "company", "operator", "manager")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0",
            (user["id"],),
        )
        conn.commit()
    finally:
        conn.close()
    url = f"/notifications?kind={kind}" if kind in KINDS else "/notifications"
    return RedirectResponse(url=url, status_code=303)


@router.get("/account/notify", response_class=HTMLResponse)
async def notify_settings_page(request: Request, success: str = ""):
    user = require_role(request, "seeker", "company", "operator", "manager")
    role_kinds = [k for k in ROLE_KINDS[user["role"]] if k != "system"]
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT notify_settings FROM users WHERE id=?", (user["id"],)
        ).fetchone()
    finally:
        conn.close()
    settings = json.loads(row["notify_settings"])
    toggles = [
        {"kind": k, "label": KINDS[k], "on": settings.get(k, True) is not False}
        for k in role_kinds
    ]
    return templates.TemplateResponse(
        request=request, name="account/notify.html", context={
            "request": request, "page_title": "알림 설정",
            "user_name": user["name"], "user_role": user["role"],
            "toggles": toggles, "success": success,
        }
    )


@router.post("/account/notify")
async def notify_settings_save(request: Request):
    user = require_role(request, "seeker", "company", "operator", "manager")
    role_kinds = [k for k in ROLE_KINDS[user["role"]] if k != "system"]
    form = await request.form()
    settings = {k: form.get(k) == "on" for k in role_kinds}
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE users SET notify_settings=? WHERE id=?",
            (json.dumps(settings), user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/account/notify?success=1", status_code=303)
