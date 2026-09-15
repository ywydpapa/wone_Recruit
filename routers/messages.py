from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from core.db import get_sqlite
from core.deps import check_login, templates

router = APIRouter()


def _get_session_user(request):
    return {
        "id": request.session["id"],
        "name": request.session.get("name", ""),
        "role": request.session.get("role", ""),
    }


@router.get("/messages", response_class=HTMLResponse)
async def inbox(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = _get_session_user(request)

    conn = get_sqlite()
    try:
        rows = conn.execute(
            """
            SELECT
                CASE WHEN direction='in' THEN sender ELSE recipient END AS counterpart,
                body,
                time_label,
                created_at,
                direction
            FROM messages
            WHERE user_id=?
            ORDER BY created_at DESC
            """,
            (user["id"],),
        ).fetchall()

        seen = {}
        for row in rows:
            cp = row["counterpart"]
            if cp not in seen:
                seen[cp] = {"counterpart": cp, "body": row["body"], "time_label": row["time_label"], "unread": 0}

        unread_rows = conn.execute(
            "SELECT sender, COUNT(*) AS cnt FROM messages WHERE user_id=? AND direction='in' AND is_read=0 GROUP BY sender",
            (user["id"],),
        ).fetchall()
        for r in unread_rows:
            if r["sender"] in seen:
                seen[r["sender"]]["unread"] = r["cnt"]

        convs = []
        conv_user_ids = set()
        for cp, info in seen.items():
            u = conn.execute("SELECT id FROM users WHERE name=?", (cp,)).fetchone()
            info["user_id"] = u["id"] if u else None
            if info["user_id"]:
                conv_user_ids.add(info["user_id"])
            convs.append(info)

        # 역할별 추천 연락처 조회
        contacts = []
        role = user["role"]

        if role == "seeker":
            mgr = conn.execute(
                """
                SELECT u.id, u.name
                FROM manager_assignments ma
                JOIN users u ON u.id = ma.manager_user_id
                WHERE ma.seeker_user_id = ?
                LIMIT 1
                """,
                (user["id"],),
            ).fetchone()
            if mgr and mgr["id"] not in conv_user_ids:
                contacts.append({"id": mgr["id"], "name": mgr["name"], "role_label": "담당 매니저"})

        elif role == "manager":
            seekers = conn.execute(
                """
                SELECT u.id, u.name
                FROM manager_assignments ma
                JOIN users u ON u.id = ma.seeker_user_id
                WHERE ma.manager_user_id = ?
                ORDER BY u.name
                """,
                (user["id"],),
            ).fetchall()
            for s in seekers:
                if s["id"] not in conv_user_ids:
                    contacts.append({"id": s["id"], "name": s["name"], "role_label": "구직자"})

        elif role == "operator":
            seekers = conn.execute(
                "SELECT id, name FROM users WHERE role='seeker' ORDER BY name"
            ).fetchall()
            for s in seekers:
                if s["id"] not in conv_user_ids:
                    contacts.append({"id": s["id"], "name": s["name"], "role_label": "구직자"})

    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="common/inbox.html",
        context={
            "request": request,
            "page_title": "메시지",
            "conversations": convs,
            "contacts": contacts,
        },
    )


@router.get("/messages/{counterpart_id}", response_class=HTMLResponse)
async def thread(request: Request, counterpart_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = _get_session_user(request)

    conn = get_sqlite()
    try:
        cp_row = conn.execute("SELECT name FROM users WHERE id=?", (counterpart_id,)).fetchone()
        if not cp_row:
            return RedirectResponse(url="/messages", status_code=303)
        cp_name = cp_row["name"]

        msgs = conn.execute(
            "SELECT * FROM messages WHERE user_id=? AND (sender=? OR recipient=?) ORDER BY created_at ASC",
            (user["id"], cp_name, cp_name),
        ).fetchall()

        conn.execute(
            "UPDATE messages SET is_read=1 WHERE user_id=? AND sender=? AND direction='in' AND is_read=0",
            (user["id"], cp_name),
        )
        conn.commit()
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="common/thread.html",
        context={
            "request": request,
            "page_title": cp_name,
            "messages": [dict(m) for m in msgs],
            "counterpart_name": cp_name,
            "counterpart_id": counterpart_id,
        },
    )


@router.get("/api/messages/unread-count")
async def unread_count(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "login required"}, status_code=401)
    user = _get_session_user(request)

    conn = get_sqlite()
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE user_id=? AND direction='in' AND is_read=0",
            (user["id"],),
        ).fetchone()[0]
    finally:
        conn.close()

    return JSONResponse({"count": cnt})
