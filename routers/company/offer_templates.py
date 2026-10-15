from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates

router = APIRouter(prefix="/company")


def get_templates(conn, uid):
    rows = conn.execute(
        "SELECT id, name, title, message, contact, updated_at FROM offer_templates "
        "WHERE company_user_id=? ORDER BY updated_at DESC",
        (uid,),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/offer-templates", response_class=HTMLResponse)
async def offer_templates(request: Request, edit: int = 0, saved: str = ""):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        tpls = get_templates(conn, user["id"])
    finally:
        conn.close()
    cur = next((t for t in tpls if t["id"] == edit), None)
    return templates.TemplateResponse(
        request=request, name="company/offer_templates.html", context={
            "request": request, "page_title": "메시지 양식",
            "user_name": user["name"], "user_role": "company",
            "offer_tpls": tpls, "cur": cur, "saved": saved,
        }
    )


# ajax는 제안 창의 양식 저장 요청임. 목록 갱신용 JSON 반환
@router.post("/offer-templates")
async def offer_template_save(
    request: Request,
    name: str = Form(""),
    title: str = Form(""),
    message: str = Form(""),
    contact: str = Form(""),
    tpl_id: int = Form(0),
    ajax: str = Form(""),
):
    user = require_role(request, "company")
    name, title, message, contact = name.strip()[:50], title.strip()[:200], message.strip()[:3000], contact.strip()[:100]
    if not (name and title and message):
        if ajax:
            return JSONResponse({"error": "양식 이름, 제목, 내용을 모두 입력해 주세요"}, status_code=400)
        return RedirectResponse(url="/company/offer-templates?saved=empty", status_code=303)
    conn = get_sqlite()
    try:
        if tpl_id:
            conn.execute(
                "UPDATE offer_templates SET name=?, title=?, message=?, contact=?, updated_at=datetime('now','localtime') "
                "WHERE id=? AND company_user_id=?",
                (name, title, message, contact, tpl_id, user["id"]),
            )
        else:
            tpl_id = conn.execute(
                "INSERT INTO offer_templates (company_user_id, name, title, message, contact) VALUES (?,?,?,?,?)",
                (user["id"], name, title, message, contact),
            ).lastrowid
        conn.commit()
    finally:
        conn.close()
    if ajax:
        return JSONResponse({"id": tpl_id, "name": name, "title": title, "message": message, "contact": contact})
    return RedirectResponse(url="/company/offer-templates?saved=1", status_code=303)


@router.delete("/offer-templates/{tpl_id}")
async def offer_template_delete(request: Request, tpl_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        conn.execute(
            "DELETE FROM offer_templates WHERE id=? AND company_user_id=?", (tpl_id, user["id"])
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"redirect": "/company/offer-templates"})
