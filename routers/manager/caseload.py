import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification


def _parse_json_list(val):
    if not val or val == '[]':
        return '-'
    try:
        items = json.loads(val)
        return ', '.join(items) if items else '-'
    except (json.JSONDecodeError, TypeError):
        return val


router = APIRouter()


STAGE_LABELS = {
    "counseling": "상담중",
    "matching": "매칭중",
    "interview": "면접",
    "placed": "배치",
    "settled": "정착",
}


@router.get("/seekers", response_class=HTMLResponse)
async def mgr_seekers(
    request: Request,
    q: Optional[str] = Query(None),
    disability_type_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    sido: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
        sql = (
            "SELECT u.id, u.name, u.username, "
            "sp.disability_type_id, dt.name AS disability_name, "
            "sp.severity, sp.consent_sensitive, "
            "sp.mobility_type, sp.daily_work_hours, sp.work_pref, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM users u "
            "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
            "LEFT JOIN seeker_profiles sp ON u.id = sp.user_id "
            "LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id "
            "LEFT JOIN regions r ON sp.region_id = r.id "
            "WHERE ma.manager_user_id = ?"
        )
        params = [user["id"]]

        if stage == "counseling":
            sql += (" AND u.id NOT IN "
                    "(SELECT seeker_user_id FROM candidacies)")
        elif stage == "matching":
            sql += (" AND u.id IN "
                    "(SELECT seeker_user_id FROM candidacies "
                    " WHERE status IN ('pending','reviewing','shortlisted'))"
                    " AND u.id NOT IN (SELECT seeker_user_id FROM placements)")
        elif stage == "interview":
            sql += (" AND u.id IN "
                    "(SELECT seeker_user_id FROM candidacies WHERE status='interview')"
                    " AND u.id NOT IN (SELECT seeker_user_id FROM placements)")
        elif stage == "placed":
            sql += (" AND u.id IN "
                    "(SELECT seeker_user_id FROM placements "
                    " WHERE status IS NULL OR status='active')")
        elif stage == "settled":
            sql += (" AND u.id IN "
                    "(SELECT seeker_user_id FROM placements WHERE status='settled')")

        if q:
            sql += " AND (u.name LIKE ? OR u.username LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if disability_type_id:
            sql += " AND sp.disability_type_id=?"
            params.append(disability_type_id)
        if severity:
            sql += " AND sp.severity=?"
            params.append(severity)
        if sido:
            sql += " AND r.sido=?"
            params.append(sido)
        sql += " ORDER BY u.id"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        seekers = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if disability_type_id: qs_parts.append(f"disability_type_id={disability_type_id}")
    if severity: qs_parts.append(f"severity={severity}")
    if sido: qs_parts.append(f"sido={sido}")
    if stage: qs_parts.append(f"stage={stage}")
    stage_label = STAGE_LABELS.get(stage, "")
    return templates.TemplateResponse(
        request=request, name="manager/seekers.html", context={
            "request": request,
            "page_title": f"담당 구직자 - {stage_label}" if stage_label else "내 담당 구직자",
            "user_name": user["name"], "user_role": "manager",
            "seekers": seekers,
            "disability_types": disability_types,
            "q": q or "",
            "selected_disability": disability_type_id or "",
            "selected_severity": severity or "",
            "selected_sido": sido or "",
            "selected_stage": stage or "",
            "stage_label": stage_label,
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/seekers/unassigned", response_class=HTMLResponse)
async def mgr_seekers_unassigned(
    request: Request,
    q: Optional[str] = Query(None),
    disability_type_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    sido: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
        sql = (
            "SELECT u.id, u.name, u.username, "
            "sp.disability_type_id, dt.name AS disability_name, "
            "sp.severity, sp.consent_sensitive, "
            "sp.mobility_type, sp.daily_work_hours, sp.work_pref, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM users u "
            "LEFT JOIN seeker_profiles sp ON u.id = sp.user_id "
            "LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id "
            "LEFT JOIN regions r ON sp.region_id = r.id "
            "WHERE u.role = 'seeker' "
            "AND u.id NOT IN (SELECT seeker_user_id FROM manager_assignments)"
        )
        params = []
        if q:
            sql += " AND (u.name LIKE ? OR u.username LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if disability_type_id:
            sql += " AND sp.disability_type_id=?"
            params.append(disability_type_id)
        if severity:
            sql += " AND sp.severity=?"
            params.append(severity)
        if sido:
            sql += " AND r.sido=?"
            params.append(sido)
        sql += " ORDER BY u.id"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        seekers = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if disability_type_id: qs_parts.append(f"disability_type_id={disability_type_id}")
    if severity: qs_parts.append(f"severity={severity}")
    if sido: qs_parts.append(f"sido={sido}")
    return templates.TemplateResponse(
        request=request, name="manager/seekers_unassigned.html", context={
            "request": request, "page_title": "미배정 구직자",
            "user_name": user["name"], "user_role": "manager",
            "seekers": seekers,
            "disability_types": disability_types,
            "q": q or "",
            "selected_disability": disability_type_id or "",
            "selected_severity": severity or "",
            "selected_sido": sido or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.post("/seekers/{seeker_id}/claim")
async def mgr_claim_seeker(request: Request, seeker_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        seeker = conn.execute("SELECT id FROM users WHERE id=? AND role='seeker'", (seeker_id,)).fetchone()
        if not seeker:
            raise HTTPException(status_code=400, detail="유효하지 않은 구직자입니다.")
        conn.execute(
            "INSERT OR IGNORE INTO manager_assignments (manager_user_id, seeker_user_id, assigned_by) VALUES (?,?,?)",
            (user["id"], seeker_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/mgr/seekers", status_code=303)


@router.get("/seekers/{user_id}", response_class=HTMLResponse)
async def mgr_seeker_detail(request: Request, user_id: int):
    user = require_role(request, "manager")
    conn = get_sqlite()
    try:
        seeker = conn.execute(
            "SELECT * FROM users WHERE id=? AND role='seeker'", (user_id,)
        ).fetchone()
        if not seeker:
            raise HTTPException(status_code=404, detail="구직자를 찾을 수 없습니다.")
        profile = conn.execute(
            """SELECT sp.*, dt.name AS disability_name,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM seeker_profiles sp
               LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id
               LEFT JOIN regions r ON sp.region_id = r.id
               WHERE sp.user_id = ?""",
            (user_id,),
        ).fetchone()
        certifications = conn.execute(
            "SELECT * FROM seeker_certifications WHERE user_id=? ORDER BY id",
            (user_id,),
        ).fetchall()
        # 상담 타임라인
        sessions = conn.execute(
            "SELECT cs.*, u.name AS manager_name "
            "FROM consultation_sessions cs "
            "JOIN users u ON cs.manager_user_id = u.id "
            "WHERE cs.seeker_user_id=? ORDER BY cs.created_at DESC",
            (user_id,),
        ).fetchall()
        # 초기 평가
        assessment = conn.execute(
            "SELECT c.*, u.name AS operator_name "
            "FROM consultations c JOIN users u ON c.operator_user_id = u.id "
            "WHERE c.seeker_user_id=? ORDER BY c.created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        # 지원 현황 (동의한 경우만)
        consent_given = profile and profile["consent_sensitive"]
        candidacies = []
        if consent_given:
            candidacies = conn.execute(
                """SELECT c.id, c.job_id, c.status, c.match_stage, c.created_at,
                          jp.title AS job_title, jp.company_id, co.company_name
                   FROM candidacies c
                   JOIN job_postings jp ON c.job_id = jp.id
                   JOIN companies co ON jp.company_id = co.id
                   WHERE c.seeker_user_id=?
                   ORDER BY c.created_at DESC""",
                (user_id,),
            ).fetchall()
        # 열람 기록
        conn.execute(
            "INSERT INTO access_log (viewer_id, seeker_user_id, purpose) VALUES (?,?,?)",
            (user["id"], user_id, "manager_view"),
        )
        conn.commit()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="manager/seeker_detail.html", context={
            "request": request, "page_title": f"구직자 상세 - {seeker['name']}",
            "user_name": user["name"], "user_role": "manager",
            "seeker": seeker,
            "profile": profile,
            "certifications": certifications,
            "sessions": sessions,
            "assessment": assessment,
            "candidacies": candidacies,
            "consent_given": consent_given,
            "communication_pref_display": _parse_json_list(profile["communication_pref"]) if profile else '-',
            "assistive_tech_display": _parse_json_list(profile["assistive_tech"]) if profile else '-',
            "accommodation_needs_display": _parse_json_list(profile["accommodation_needs"]) if profile else '-',
        }
    )
