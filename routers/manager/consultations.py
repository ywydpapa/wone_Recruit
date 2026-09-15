from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates

router = APIRouter()

SESSION_TYPE_LABELS = {
    'initial_assessment': '초기 평가',
    'career_counseling': '진로 상담',
    'interview_prep': '면접 준비',
    'followup_call': '후속 통화',
    'company_visit': '기업 방문',
    'other': '기타',
}


@router.get("/consultations/new", response_class=HTMLResponse)
async def mgr_consultation_new(request: Request, seeker_id: int = Query(...)):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        seeker = conn.execute("SELECT * FROM users WHERE id=? AND role='seeker'", (seeker_id,)).fetchone()
    finally:
        conn.close()
    if not seeker:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request=request, name="manager/consultation_form.html", context={
            "request": request, "page_title": "상담 기록 작성",
            "user_name": user["name"], "user_role": "manager",
            "seeker": seeker, "consultation": None,
            "session_types": SESSION_TYPE_LABELS,
        }
    )


@router.post("/consultations")
async def mgr_consultation_create(
    request: Request,
    seeker_id: int = Form(...),
    session_type: str = Form("other"),
    notes: str = Form(""),
):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO consultation_sessions (seeker_user_id, manager_user_id, session_type, notes) VALUES (?,?,?,?)",
            (seeker_id, user["id"], session_type, notes.strip()),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/seekers/{seeker_id}", status_code=303)


@router.get("/consultations/{session_id}/edit", response_class=HTMLResponse)
async def mgr_consultation_edit(request: Request, session_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT * FROM consultation_sessions WHERE id=?", (session_id,)).fetchone()
        if not row or row["manager_user_id"] != user["id"]:
            raise HTTPException(status_code=404)
        seeker = conn.execute("SELECT * FROM users WHERE id=?", (row["seeker_user_id"],)).fetchone()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="manager/consultation_form.html", context={
            "request": request, "page_title": "상담 기록 수정",
            "user_name": user["name"], "user_role": "manager",
            "seeker": seeker, "consultation": row,
            "session_types": SESSION_TYPE_LABELS,
        }
    )


@router.post("/consultations/{session_id}")
async def mgr_consultation_update(
    request: Request,
    session_id: int,
    seeker_id: int = Form(...),
    session_type: str = Form("other"),
    notes: str = Form(""),
):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE consultation_sessions SET session_type=?, notes=? WHERE id=? AND manager_user_id=?",
            (session_type, notes.strip(), session_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/seekers/{seeker_id}", status_code=303)


@router.post("/consultations/{session_id}/delete")
async def mgr_consultation_delete(request: Request, session_id: int):
    user = require_role(request, "manager")
    form = await request.form()
    seeker_id = form.get("seeker_id")
    conn = get_sqlite()
    try:
        conn.execute(
            "DELETE FROM consultation_sessions WHERE id=? AND manager_user_id=?",
            (session_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/seekers/{seeker_id}", status_code=303)
