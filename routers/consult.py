from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.notifications import create_notification
from core.constants import CONSULT_CATEGORIES, CONSULT_METHODS, CONSULT_REQ_STATUS
from routers.manager.consultations import SESSION_TYPE_LABELS, METHOD_LABELS, CONSULT_STATUS_LABELS

router = APIRouter()

CONTENT_MAX = 2000

CATEGORY_ICONS = {
    "job": "fa-briefcase",
    "device": "fa-wheelchair",
    "work": "fa-triangle-exclamation",
    "rights": "fa-scale-balanced",
    "etc": "fa-ellipsis",
}

ERROR_MESSAGES = {
    "bad_category": "상담 분야를 선택해 주세요.",
    "content_required": "상담 내용을 입력해 주세요.",
    "content_too_long": f"상담 내용은 {CONTENT_MAX}자 이내로 입력해 주세요.",
    "bad_method": "상담 방법을 선택해 주세요.",
}


def check_form(category, content, method):
    if category not in CONSULT_CATEGORIES:
        return "bad_category"
    if not content:
        return "content_required"
    if len(content) > CONTENT_MAX:
        return "content_too_long"
    if method not in CONSULT_METHODS:
        return "bad_method"
    return None


def notify_new_request(conn, user, req_id):
    msg = f"{user['name']}님이 상담을 신청했습니다"
    ma = conn.execute(
        "SELECT manager_user_id FROM manager_assignments WHERE seeker_user_id=?",
        (user["id"],),
    ).fetchone()
    if ma:
        create_notification(
            conn, ma["manager_user_id"],
            msg,
            f"/mgr/consult-requests/{req_id}", kind="consult",
        )
    else:
        ops = conn.execute("SELECT id FROM users WHERE role='operator'").fetchall()
        for op in ops:
            create_notification(
                conn, op["id"],
                msg,
                f"/op/seekers/{user['id']}", kind="consult",
            )


@router.get("/consult", response_class=HTMLResponse)
async def consult_list(request: Request):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        req_rows = conn.execute(
            "SELECT * FROM consult_requests WHERE seeker_user_id=? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
        session_rows = conn.execute(
            "SELECT * FROM consultation_sessions WHERE seeker_user_id=? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
        manager = conn.execute(
            "SELECT u.name FROM manager_assignments ma JOIN users u ON ma.manager_user_id=u.id "
            "WHERE ma.seeker_user_id=?",
            (user["id"],),
        ).fetchone()
    finally:
        conn.close()

    reqs = []
    for r in req_rows:
        d = dict(r)
        d["category_label"] = CONSULT_CATEGORIES[d["category"]]
        d["method_label"] = CONSULT_METHODS[d["method"]]
        d["status_label"], d["status_color"] = CONSULT_REQ_STATUS[d["status"]]
        reqs.append(d)

    sessions = []
    for s in session_rows:
        d = dict(s)
        d["type_label"] = SESSION_TYPE_LABELS[d["session_type"]]
        d["method_label"] = METHOD_LABELS[d["method"]]
        d["status_label"] = CONSULT_STATUS_LABELS[d["status"]]
        sessions.append(d)

    return templates.TemplateResponse(
        request=request, name="consult/list.html", context={
            "request": request, "page_title": "상담 내역",
            "user_name": user["name"], "user_role": "seeker",
            "reqs": reqs, "sessions": sessions,
            "manager": manager,
        }
    )


@router.get("/consult/new", response_class=HTMLResponse)
async def consult_new_form(request: Request, category: str = Query(""), error: str = Query(None)):
    user = require_role(request, "seeker")
    return templates.TemplateResponse(
        request=request, name="consult/form.html", context={
            "request": request, "page_title": "상담 신청",
            "user_name": user["name"], "user_role": "seeker",
            "categories": CONSULT_CATEGORIES,
            "category_icons": CATEGORY_ICONS,
            "methods": CONSULT_METHODS,
            "selected_category": category,
            "error_msg": ERROR_MESSAGES.get(error),
        }
    )


@router.post("/consult")
async def consult_create(
    request: Request,
    category: str = Form("job"),
    content: str = Form(""),
    method: str = Form("phone"),
    preferred_time: str = Form(""),
):
    user = require_role(request, "seeker")
    content = content.strip()
    err = check_form(category, content, method)
    if err:
        qs = f"&category={category}" if category in CONSULT_CATEGORIES else ""
        return RedirectResponse(url=f"/consult/new?error={err}{qs}", status_code=303)

    conn = get_sqlite()
    try:
        cur = conn.execute(
            "INSERT INTO consult_requests (seeker_user_id, category, content, method, preferred_time) "
            "VALUES (?,?,?,?,?)",
            (user["id"], category, content, method, preferred_time.strip()),
        )
        notify_new_request(conn, user, cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/consult", status_code=303)


@router.post("/consult/{req_id}/cancel")
async def consult_cancel(request: Request, req_id: int):
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE consult_requests SET status='cancelled' WHERE id=? AND seeker_user_id=? AND status='pending'",
            (req_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/consult", status_code=303)
