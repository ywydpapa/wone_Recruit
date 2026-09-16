from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates

router = APIRouter()

FOLLOWUP_LABELS = {'1w': '1주차', '1m': '1개월차', '3m': '3개월차', '6m': '6개월차'}
PLACEMENT_STATUS = {'active': '적응중', 'settled': '정착', 'departed': '이탈'}


@router.get("/placements", response_class=HTMLResponse)
async def mgr_placements(request: Request, company: Optional[int] = Query(None)):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        sql = """SELECT p.*, u.name AS seeker_name, jp.title AS job_title,
                      c.company_name, sp.disability_type_id,
                      dt.name AS disability_name, sp.severity
               FROM placements p
               JOIN users u ON p.seeker_user_id = u.id
               JOIN job_postings jp ON p.job_id = jp.id
               JOIN companies c ON p.company_id = c.id
               LEFT JOIN seeker_profiles sp ON p.seeker_user_id = sp.user_id
               LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id
               WHERE p.seeker_user_id IN (
                   SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id = ?
               )"""
        params = [user["id"]]
        if company:
            sql += " AND p.company_id = ?"
            params.append(company)
        sql += " ORDER BY p.created_at DESC"
        placements = conn.execute(sql, params).fetchall()
        # 사후관리 요약
        followup_summary = {}
        for p in placements:
            row = conn.execute(
                """SELECT
                       COALESCE(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END), 0) AS done,
                       COALESCE(SUM(CASE WHEN status='overdue' THEN 1 ELSE 0 END), 0) AS overdue,
                       COUNT(*) AS total
                   FROM placement_followups WHERE placement_id=?""",
                (p["id"],),
            ).fetchone()
            followup_summary[p["id"]] = dict(row) if row else {"done": 0, "overdue": 0, "total": 0}
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="manager/placements.html", context={
            "request": request, "page_title": "배치 관리",
            "user_name": user["name"], "user_role": "manager",
            "placements": placements,
            "followup_summary": followup_summary,
            "placement_status": PLACEMENT_STATUS,
        }
    )


@router.get("/placements/{placement_id}", response_class=HTMLResponse)
async def mgr_placement_detail(request: Request, placement_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        placement = conn.execute(
            """SELECT p.*, u.name AS seeker_name, jp.title AS job_title,
                      c.company_name
               FROM placements p
               JOIN users u ON p.seeker_user_id = u.id
               JOIN job_postings jp ON p.job_id = jp.id
               JOIN companies c ON p.company_id = c.id
               WHERE p.id = ?""",
            (placement_id,),
        ).fetchone()
        if not placement:
            raise HTTPException(status_code=404)
        # 지연 follow-up 자동 갱신
        conn.execute(
            "UPDATE placement_followups SET status='overdue' WHERE placement_id=? AND status='pending' AND due_date < date('now','localtime')",
            (placement_id,),
        )
        conn.commit()
        followups = conn.execute(
            "SELECT * FROM placement_followups WHERE placement_id=? ORDER BY due_date",
            (placement_id,),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="manager/placement_detail.html", context={
            "request": request, "page_title": f"배치 상세 - {placement['seeker_name']}",
            "user_name": user["name"], "user_role": "manager",
            "placement": placement,
            "followups": followups,
            "followup_labels": FOLLOWUP_LABELS,
            "placement_status": PLACEMENT_STATUS,
        }
    )


@router.post("/placements/{placement_id}/status")
async def mgr_placement_status(
    request: Request,
    placement_id: int,
    status: str = Form(...),
):
    user = require_role(request, "manager")
    if status not in PLACEMENT_STATUS:
        raise HTTPException(status_code=400)
    conn = get_sqlite()
    try:
        end_date = "date('now','localtime')" if status == "departed" else "NULL"
        conn.execute(
            f"UPDATE placements SET status=?, end_date={end_date} WHERE id=?",
            (status, placement_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/placements/{placement_id}", status_code=303)


@router.post("/placements/{placement_id}/followup/{followup_id}")
async def mgr_followup_complete(
    request: Request,
    placement_id: int,
    followup_id: int,
    notes: str = Form(""),
):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        conn.execute(
            """UPDATE placement_followups
               SET status='completed', notes=?, completed_at=datetime('now','localtime'), completed_by=?
               WHERE id=? AND placement_id=?""",
            (notes.strip(), user["id"], followup_id, placement_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/placements/{placement_id}", status_code=303)
