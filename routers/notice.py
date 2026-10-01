from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.notices import audience_sql
from core.pagination import page_info, PER_PAGE

router = APIRouter()

AUDIENCE_LABELS = {"all": "전체", "seeker": "구직자", "company": "기업"}
TITLE_MAX = 200
CONTENT_MAX = 5000

ERROR_MESSAGES = {
    "title_required": "제목을 입력해 주세요.",
    "content_required": "내용을 입력해 주세요.",
    "title_too_long": f"제목은 {TITLE_MAX}자 이내로 입력해 주세요.",
    "content_too_long": f"내용은 {CONTENT_MAX}자 이내로 입력해 주세요.",
    "bad_audience": "대상 값이 올바르지 않습니다.",
}


def check_form(title, content, audience):
    if not title:
        return "title_required"
    if not content:
        return "content_required"
    if len(title) > TITLE_MAX:
        return "title_too_long"
    if len(content) > CONTENT_MAX:
        return "content_too_long"
    if audience not in AUDIENCE_LABELS:
        return "bad_audience"
    return None


@router.get("/op/notices", response_class=HTMLResponse)
async def op_notice_list(request: Request, q: str = Query(None), page: int = Query(1)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = "SELECT * FROM notices WHERE 1=1"
        params = []
        if q:
            sql += " AND title LIKE ?"
            params.append(f"%{q}%")
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        offset = (page - 1) * PER_PAGE
        rows = conn.execute(
            sql + " ORDER BY pinned DESC, created_at DESC LIMIT ? OFFSET ?",
            params + [PER_PAGE, offset],
        ).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()

    cutoff = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    notices = []
    for i, row in enumerate(rows):
        d = dict(row)
        d["no"] = total - offset - i
        d["audience_label"] = AUDIENCE_LABELS.get(d["audience"], d["audience"])
        d["new"] = d["created_at"] >= cutoff
        notices.append(d)

    return templates.TemplateResponse(
        request=request, name="op/notices.html", context={
            "request": request, "page_title": "공지 관리",
            "user_name": user["name"], "user_role": "operator",
            "notices": notices,
            "q": q or "",
            "pagination": pagination, "base_qs": urlencode({"q": q}) if q else "",
        }
    )


@router.get("/op/notices/new", response_class=HTMLResponse)
async def op_notice_new(request: Request, error: str = Query(None)):
    user = require_role(request, "operator")
    return templates.TemplateResponse(
        request=request, name="op/notice_form.html", context={
            "request": request, "page_title": "공지 작성",
            "user_name": user["name"], "user_role": "operator",
            "notice": None,
            "audience_labels": AUDIENCE_LABELS,
            "error_msg": ERROR_MESSAGES.get(error),
        }
    )


@router.post("/op/notices", response_class=HTMLResponse)
async def op_notice_create(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    audience: str = Form("all"),
    pinned: str = Form(None),
):
    user = require_role(request, "operator")
    title = title.strip()
    content = content.strip()
    err = check_form(title, content, audience)
    if err:
        return RedirectResponse(url=f"/op/notices/new?error={err}", status_code=303)

    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO notices (title, content, audience, pinned, author_id) VALUES (?,?,?,?,?)",
            (title, content, audience, 1 if pinned == "on" else 0, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/op/notices", status_code=303)


@router.get("/op/notices/{notice_id}/edit", response_class=HTMLResponse)
async def op_notice_edit(request: Request, notice_id: int, error: str = Query(None)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        notice = conn.execute("SELECT * FROM notices WHERE id=?", (notice_id,)).fetchone()
    finally:
        conn.close()
    if notice is None:
        raise HTTPException(status_code=404, detail="공지를 찾을 수 없습니다.")
    return templates.TemplateResponse(
        request=request, name="op/notice_form.html", context={
            "request": request, "page_title": "공지 수정",
            "user_name": user["name"], "user_role": "operator",
            "notice": notice,
            "audience_labels": AUDIENCE_LABELS,
            "error_msg": ERROR_MESSAGES.get(error),
        }
    )


@router.post("/op/notices/{notice_id}", response_class=HTMLResponse)
async def op_notice_update(
    request: Request,
    notice_id: int,
    title: str = Form(...),
    content: str = Form(...),
    audience: str = Form("all"),
    pinned: str = Form(None),
):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        notice = conn.execute("SELECT id FROM notices WHERE id=?", (notice_id,)).fetchone()
        if notice is None:
            raise HTTPException(status_code=404, detail="공지를 찾을 수 없습니다.")

        title = title.strip()
        content = content.strip()
        err = check_form(title, content, audience)
        if err:
            return RedirectResponse(url=f"/op/notices/{notice_id}/edit?error={err}", status_code=303)

        conn.execute(
            "UPDATE notices SET title=?, content=?, audience=?, pinned=?, updated_at=datetime('now','localtime') WHERE id=?",
            (title, content, audience, 1 if pinned == "on" else 0, notice_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/op/notices", status_code=303)


@router.post("/op/notices/{notice_id}/delete")
async def op_notice_delete(request: Request, notice_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute("DELETE FROM notices WHERE id=?", (notice_id,))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/op/notices", status_code=303)


@router.get("/notices", response_class=HTMLResponse)
async def notice_list(request: Request, q: str = Query(None), page: int = Query(1)):
    user = require_role(request, "seeker", "company", "manager", "operator")
    role = user["role"]
    conn = get_sqlite()
    try:
        sql = f"SELECT * FROM notices WHERE {audience_sql(role)}"
        params = []
        if q:
            sql += " AND title LIKE ?"
            params.append(f"%{q}%")
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        pinned_total = conn.execute(f"SELECT COUNT(*) FROM ({sql + ' AND pinned=1'})", params).fetchone()[0]
        normal_total = total - pinned_total
        offset = (page - 1) * PER_PAGE
        rows = conn.execute(
            sql + " ORDER BY pinned DESC, created_at DESC LIMIT ? OFFSET ?",
            params + [PER_PAGE, offset],
        ).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()

    cutoff = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    notices = []
    for i, row in enumerate(rows):
        d = dict(row)
        if d["pinned"]:
            d["no"] = None
        else:
            normal_idx = offset + i - pinned_total
            d["no"] = normal_total - normal_idx
        d["new"] = d["created_at"] >= cutoff
        notices.append(d)

    return templates.TemplateResponse(
        request=request, name="notice/list.html", context={
            "request": request, "page_title": "공지사항",
            "user_name": user["name"], "user_role": role,
            "notices": notices,
            "q": q or "",
            "pagination": pagination, "base_qs": urlencode({"q": q}) if q else "",
        }
    )


@router.get("/notices/{notice_id}", response_class=HTMLResponse)
async def notice_detail(request: Request, notice_id: int):
    user = require_role(request, "seeker", "company", "manager", "operator")
    role = user["role"]
    conn = get_sqlite()
    try:
        clause = audience_sql(role)
        notice = conn.execute(
            f"SELECT * FROM notices WHERE id=? AND {clause}", (notice_id,)
        ).fetchone()
        if notice is None:
            return RedirectResponse(url="/notices", status_code=303)

        conn.execute("UPDATE notices SET views = views + 1 WHERE id=?", (notice_id,))
        conn.commit()

        prev_row = conn.execute(
            f"SELECT id, title FROM notices WHERE id<? AND {clause} ORDER BY id DESC LIMIT 1",
            (notice_id,),
        ).fetchone()
        next_row = conn.execute(
            f"SELECT id, title FROM notices WHERE id>? AND {clause} ORDER BY id ASC LIMIT 1",
            (notice_id,),
        ).fetchone()
    finally:
        conn.close()

    notice = dict(notice)
    notice["views"] += 1
    notice["audience_label"] = AUDIENCE_LABELS.get(notice["audience"], notice["audience"])

    return templates.TemplateResponse(
        request=request, name="notice/detail.html", context={
            "request": request, "page_title": notice["title"],
            "user_name": user["name"], "user_role": role,
            "notice": notice,
            "prev": prev_row,
            "next": next_row,
        }
    )
