from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.notifications import create_notification
from core.constants import CONSULT_CATEGORIES, CONSULT_METHODS, CONSULT_REQ_STATUS

router = APIRouter()

TABS = [
    ("active", "전체 진행중"),
    ("pending", "접수"),
    ("accepted", "확인"),
    ("scheduled", "일정 확정"),
    ("done", "완료"),
    ("cancelled", "취소"),
]

PREVIEW_LEN = 60


def _get_req(conn, req_id, manager_id):
    row = conn.execute(
        "SELECT cr.*, u.name AS seeker_name, u.phone AS seeker_phone "
        "FROM consult_requests cr "
        "JOIN manager_assignments ma ON ma.seeker_user_id = cr.seeker_user_id "
        "JOIN users u ON u.id = cr.seeker_user_id "
        "WHERE cr.id=? AND ma.manager_user_id=?",
        (req_id, manager_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404)
    return row


def _decorate(row):
    r = dict(row)
    r["category_label"] = CONSULT_CATEGORIES[r["category"]]
    r["method_label"] = CONSULT_METHODS[r["method"]]
    r["status_label"], r["status_color"] = CONSULT_REQ_STATUS[r["status"]]
    return r


@router.get("/consult-requests", response_class=HTMLResponse)
async def mgr_consult_requests(request: Request, status: str = Query("active")):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        by_status = {r["status"]: r["cnt"] for r in conn.execute(
            "SELECT cr.status, COUNT(*) AS cnt FROM consult_requests cr "
            "JOIN manager_assignments ma ON ma.seeker_user_id = cr.seeker_user_id "
            "WHERE ma.manager_user_id=? GROUP BY cr.status",
            (user["id"],),
        ).fetchall()}
        counts = {k: by_status.get(k, 0) for k, _ in TABS[1:]}
        counts["active"] = counts["pending"] + counts["accepted"] + counts["scheduled"]

        sql = (
            "SELECT cr.*, u.name AS seeker_name FROM consult_requests cr "
            "JOIN manager_assignments ma ON ma.seeker_user_id = cr.seeker_user_id "
            "JOIN users u ON u.id = cr.seeker_user_id "
            "WHERE ma.manager_user_id=?"
        )
        params = [user["id"]]
        if status == "active":
            sql += " AND cr.status IN ('pending','accepted','scheduled')"
        elif status in CONSULT_REQ_STATUS:
            sql += " AND cr.status=?"
            params.append(status)
        sql += (
            " ORDER BY CASE WHEN cr.status='pending' THEN 0 ELSE 1 END, cr.created_at DESC"
        )
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    reqs = []
    for row in rows:
        r = _decorate(row)
        content = r["content"]
        r["content_preview"] = content if len(content) <= PREVIEW_LEN else content[:PREVIEW_LEN] + "..."
        reqs.append(r)

    return templates.TemplateResponse(
        request=request, name="manager/consult_requests.html", context={
            "request": request, "page_title": "상담 요청",
            "user_name": user["name"], "user_role": "manager",
            "reqs": reqs,
            "tabs": TABS,
            "counts": counts,
            "selected": status,
        }
    )


@router.get("/consult-requests/{req_id}", response_class=HTMLResponse)
async def mgr_consult_request_detail(request: Request, req_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        req = _get_req(conn, req_id, user["id"])
        history = conn.execute(
            "SELECT * FROM consult_requests WHERE seeker_user_id=? AND id != ? ORDER BY created_at DESC",
            (req["seeker_user_id"], req_id),
        ).fetchall()
    finally:
        conn.close()

    req = _decorate(req)
    history = [_decorate(h) for h in history]

    return templates.TemplateResponse(
        request=request, name="manager/consult_request_detail.html", context={
            "request": request, "page_title": "상담 요청 상세",
            "user_name": user["name"], "user_role": "manager",
            "req": req,
            "history": history,
        }
    )


@router.post("/consult-requests/{req_id}/accept")
async def mgr_consult_request_accept(request: Request, req_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        req = _get_req(conn, req_id, user["id"])
        if req["status"] == "pending":
            conn.execute(
                "UPDATE consult_requests SET status='accepted', manager_user_id=?, "
                "handled_at=datetime('now','localtime') WHERE id=?",
                (user["id"], req_id),
            )
            create_notification(conn, req["seeker_user_id"], "상담 신청이 확인되었습니다", "/consult", kind="consult")
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/consult-requests/{req_id}", status_code=303)


@router.post("/consult-requests/{req_id}/reply")
async def mgr_consult_request_reply(request: Request, req_id: int, reply: str = Form(...)):
    user = require_role(request, "manager")
    reply = reply.strip()[:2000]
    if not reply:
        raise HTTPException(status_code=400, detail="답변을 입력해주세요.")
    conn = get_sqlite()
    try:
        req = _get_req(conn, req_id, user["id"])
        if req["status"] in ("pending", "accepted", "scheduled"):
            conn.execute(
                "UPDATE consult_requests SET status='done', reply=?, manager_user_id=?, "
                "handled_at=COALESCE(handled_at, datetime('now','localtime')) WHERE id=?",
                (reply, user["id"], req_id),
            )
            create_notification(conn, req["seeker_user_id"], "상담 답변이 등록되었습니다", "/consult", kind="consult")
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/consult-requests/{req_id}", status_code=303)
