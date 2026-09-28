from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.pagination import page_info, PER_PAGE

router = APIRouter()

INQUIRY_CATEGORIES = [
    "계정/로그인", "공고/지원", "매칭/추천", "기업인증",
    "이용방법", "오류/불편", "기타",
]


@router.get("/inquiries", response_class=HTMLResponse)
async def inquiry_list(request: Request, page: int = Query(1)):
    role = request.session.get("role")
    if role not in ("seeker", "company"):
        return RedirectResponse(url="/login", status_code=303)
    user = require_role(request, role)
    conn = get_sqlite()
    try:
        page = max(1, page)
        total = conn.execute(
            "SELECT COUNT(*) FROM inquiries WHERE user_id=?", (user["id"],)
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM inquiries WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user["id"], PER_PAGE, (page - 1) * PER_PAGE),
        ).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="inquiry/list.html", context={
            "request": request, "page_title": "내 문의",
            "user_name": user["name"], "user_role": role,
            "inquiries": rows,
            "categories": INQUIRY_CATEGORIES,
            "pagination": pagination, "base_qs": "",
        }
    )


@router.post("/inquiries", response_class=HTMLResponse)
async def inquiry_submit(
    request: Request,
    category: str = Form(""),
    subject: str = Form(...),
    content: str = Form(...),
):
    role = request.session.get("role")
    if role not in ("seeker", "company"):
        return RedirectResponse(url="/login", status_code=303)
    user = require_role(request, role)
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO inquiries (user_id, category, subject, content) VALUES (?,?,?,?)",
            (user["id"], category, subject.strip(), content.strip()),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/inquiries", status_code=303)


@router.get("/inquiries/{inquiry_id}", response_class=HTMLResponse)
async def inquiry_detail(request: Request, inquiry_id: int):
    role = request.session.get("role")
    if role not in ("seeker", "company"):
        return RedirectResponse(url="/login", status_code=303)
    user = require_role(request, role)
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT * FROM inquiries WHERE id=? AND user_id=?",
            (inquiry_id, user["id"]),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return RedirectResponse(url="/inquiries", status_code=303)
    return templates.TemplateResponse(
        request=request, name="inquiry/detail.html", context={
            "request": request, "page_title": row["subject"],
            "user_name": user["name"], "user_role": role,
            "inquiry": row,
        }
    )
