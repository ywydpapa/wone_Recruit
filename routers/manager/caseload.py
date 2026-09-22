import json
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification
from core.constants import DISABILITY_ICONS, ASSISTIVE_DEVICES, STATUS_LABELS, MATCH_STAGE_LABELS
from routers.manager.consultations import SESSION_TYPE_LABELS, METHOD_LABELS, CONSULT_STATUS_LABELS


def _parse_json_list(val):
    if not val or val == '[]':
        return '-'
    try:
        items = json.loads(val)
        return ', '.join(items) if items else '-'
    except (json.JSONDecodeError, TypeError):
        return val


_DEVICE_ICON_MAP = {
    name: icon
    for devices in ASSISTIVE_DEVICES.values()
    for name, icon in devices
}

MAX_DEVICE_ICONS = 4


def _device_icons(assistive_tech_json):
    if not assistive_tech_json:
        return [], 0
    try:
        names = json.loads(assistive_tech_json)
    except (json.JSONDecodeError, TypeError):
        return [], 0
    icons = [{"name": n, "icon": _DEVICE_ICON_MAP.get(n, "fa-circle-dot")} for n in names if n]
    overflow = max(0, len(icons) - MAX_DEVICE_ICONS)
    return icons[:MAX_DEVICE_ICONS], overflow


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
            "sp.severity, sp.consent_sensitive, sp.assistive_tech, "
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
        rows = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
        dev_rows = conn.execute(
            "SELECT u.id, u.name, "
            "dt.name AS disability_name, sp.severity, sp.assistive_tech, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM users u "
            "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
            "LEFT JOIN seeker_profiles sp ON u.id = sp.user_id "
            "LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id "
            "LEFT JOIN regions r ON sp.region_id = r.id "
            "WHERE ma.manager_user_id=? AND sp.consent_sensitive=1 "
            "AND sp.assistive_tech IS NOT NULL AND sp.assistive_tech != '[]'",
            (user["id"],),
        ).fetchall()
        device_counts = {}
        device_seekers = {}
        for r in dev_rows:
            try:
                names = json.loads(r["assistive_tech"])
            except (json.JSONDecodeError, TypeError):
                continue
            sd = dict(r)
            for name in names:
                device_counts[name] = device_counts.get(name, 0) + 1
                device_seekers.setdefault(name, []).append(sd)
        device_summary = []
        for cat, devices in ASSISTIVE_DEVICES.items():
            items = [
                {"name": name, "icon": icon, "count": device_counts.get(name, 0)}
                for name, icon in devices
            ]
            device_summary.append({"category": cat, "items": items})
    finally:
        conn.close()
    seekers = []
    for s in rows:
        d = dict(s)
        d["device_icons"], d["device_overflow"] = _device_icons(s["assistive_tech"])
        seekers.append(d)
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
            "page_title": f"담당 구직자 - {stage_label}" if stage_label else "담당 구직자",
            "user_name": user["name"], "user_role": "manager",
            "seekers": seekers,
            "disability_types": disability_types,
            "q": q or "",
            "selected_disability": disability_type_id or "",
            "selected_severity": severity or "",
            "selected_sido": sido or "",
            "selected_stage": stage or "",
            "stage_label": stage_label,
            "disability_icons": DISABILITY_ICONS,
            "pagination": pagination, "base_qs": "&".join(qs_parts),
            "device_summary": device_summary,
            "device_seekers": device_seekers,
        }
    )


@router.get("/seekers/by-device", response_class=HTMLResponse)
async def mgr_seekers_by_device(
    request: Request,
    device: str = Query(""),
    page: int = Query(1),
):
    user = require_role(request, "manager")
    if not device:
        raise HTTPException(status_code=400, detail="기기명이 필요합니다.")
    conn = get_sqlite()
    try:
        like_pat = f'%"{device}"%'
        sql = (
            "SELECT u.id, u.name, u.username, "
            "sp.disability_type_id, dt.name AS disability_name, "
            "sp.severity, sp.assistive_tech, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu, "
            "sp.work_pref "
            "FROM users u "
            "JOIN manager_assignments ma ON ma.seeker_user_id = u.id "
            "LEFT JOIN seeker_profiles sp ON u.id = sp.user_id "
            "LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id "
            "LEFT JOIN regions r ON sp.region_id = r.id "
            "WHERE ma.manager_user_id = ? AND sp.consent_sensitive = 1 "
            "AND sp.assistive_tech LIKE ? "
            "ORDER BY u.id"
        )
        params = [user["id"], like_pat]
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        rows = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    seekers = []
    for s in rows:
        d = dict(s)
        d["device_icons"], d["device_overflow"] = _device_icons(s["assistive_tech"])
        seekers.append(d)
    device_icon = _DEVICE_ICON_MAP.get(device, "fa-circle-dot")
    return templates.TemplateResponse(
        request=request, name="manager/seekers_by_device.html", context={
            "request": request,
            "page_title": f"보조기기별 구직자 - {device}",
            "user_name": user["name"], "user_role": "manager",
            "seekers": seekers,
            "device": device,
            "device_icon": device_icon,
            "disability_icons": DISABILITY_ICONS,
            "pagination": pagination,
            "base_qs": f"device={device}",
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
            "sp.severity, sp.consent_sensitive, sp.assistive_tech, "
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
        rows = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    seekers = []
    for s in rows:
        d = dict(s)
        d["device_icons"], d["device_overflow"] = _device_icons(s["assistive_tech"])
        seekers.append(d)
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
            "disability_icons": DISABILITY_ICONS,
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
        sessions = conn.execute(
            "SELECT cs.*, u.name AS manager_name "
            "FROM consultation_sessions cs "
            "JOIN users u ON cs.manager_user_id = u.id "
            "WHERE cs.seeker_user_id=? ORDER BY cs.created_at DESC",
            (user_id,),
        ).fetchall()
        assessment = conn.execute(
            "SELECT c.*, u.name AS operator_name "
            "FROM consultations c JOIN users u ON c.operator_user_id = u.id "
            "WHERE c.seeker_user_id=? ORDER BY c.created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
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
        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
        selected_devices = []
        if profile and profile["assistive_tech"]:
            try:
                selected_devices = json.loads(profile["assistive_tech"])
            except (json.JSONDecodeError, TypeError):
                pass
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
            "disability_types": disability_types,
            "disability_icons": DISABILITY_ICONS,
            "assistive_devices": ASSISTIVE_DEVICES,
            "selected_devices": selected_devices,
            "certifications": certifications,
            "sessions": sessions,
            "type_labels": SESSION_TYPE_LABELS,
            "method_labels": METHOD_LABELS,
            "consult_status_labels": CONSULT_STATUS_LABELS,
            "assessment": assessment,
            "candidacies": candidacies,
            "status_labels": STATUS_LABELS,
            "stage_labels": MATCH_STAGE_LABELS,
            "consent_given": consent_given,
            "communication_pref_display": _parse_json_list(profile["communication_pref"]) if profile else '-',
            "accommodation_needs_display": _parse_json_list(profile["accommodation_needs"]) if profile else '-',
        }
    )


@router.post("/seekers/{user_id}/disability")
async def mgr_update_disability(request: Request, user_id: int):
    user = require_role(request, "manager")
    form = await request.form()
    disability_type_id = int(form.get("disability_type_id") or 0) or None
    severity = form.get("severity", "경증")
    assistive_tech = json.dumps(form.getlist("assistive_tech"), ensure_ascii=False)
    conn = get_sqlite()
    try:
        profile = conn.execute(
            "SELECT id FROM seeker_profiles WHERE user_id=?", (user_id,)
        ).fetchone()
        if not profile:
            raise HTTPException(status_code=404)
        conn.execute(
            "UPDATE seeker_profiles SET disability_type_id=?, severity=?, assistive_tech=?, updated_at=datetime('now','localtime') WHERE user_id=?",
            (disability_type_id, severity, assistive_tech, user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/mgr/seekers/{user_id}", status_code=303)
