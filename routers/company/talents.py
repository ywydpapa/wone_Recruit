import json
from typing import Optional
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.notifications import create_notification

router = APIRouter(prefix="/company")
api_router = APIRouter()


@router.get("/talents", response_class=HTMLResponse)
async def talent_search(
    request: Request,
    q: Optional[str] = Query(None),
    disability_type: Optional[str] = Query(None),
    region_id: Optional[int] = Query(None),
    sido: Optional[str] = Query(None),
    work_pref: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT sp.*, u.name AS seeker_name, dt.name AS disability_name, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM seeker_profiles sp "
            "JOIN users u ON sp.user_id=u.id "
            "LEFT JOIN disability_types dt ON sp.disability_type_id=dt.id "
            "LEFT JOIN regions r ON sp.region_id=r.id "
            "WHERE sp.consent_sensitive=1"
        )
        params = []
        if q:
            sql += " AND (u.name LIKE ? OR sp.desired_job LIKE ? OR sp.experience_summary LIKE ?)"
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        if disability_type:
            sql += " AND dt.name=?"
            params.append(disability_type)
        if region_id:
            sql += " AND sp.region_id=?"
            params.append(region_id)
        elif sido:
            sql += " AND r.sido=?"
            params.append(sido)
        if work_pref:
            sql += " AND sp.work_pref=?"
            params.append(work_pref)

        sql += " ORDER BY sp.updated_at DESC"
        page = max(1, page)
        from core.pagination import page_info, PER_PAGE
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        pagination = page_info(total, page)
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        talents = conn.execute(sql, params).fetchall()

        company = conn.execute(
            "SELECT id FROM companies WHERE user_id=?", (user["user_id"],)
        ).fetchone()
        offered_ids = set()
        if company:
            rows = conn.execute(
                "SELECT seeker_user_id FROM talent_offers WHERE company_user_id=?",
                (user["user_id"],),
            ).fetchall()
            offered_ids = {r["seeker_user_id"] for r in rows}

        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
    finally:
        conn.close()

    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if sido: qs_parts.append(f"sido={sido}")
    if disability_type: qs_parts.append(f"disability_type={disability_type}")
    if work_pref: qs_parts.append(f"work_pref={work_pref}")
    base_qs = "&".join(qs_parts)

    return templates.TemplateResponse(
        request=request,
        name="company/talents.html",
        context={
            "request": request, "page_title": "인재 검색",
            "user_name": user["user_name"], "user_role": "company",
            "talents": talents, "offered_ids": offered_ids,
            "disability_types": disability_types,
            "q": q or "", "selected_sido": sido or "",
            "selected_disability": disability_type or "",
            "selected_work_pref": work_pref or "",
            "pagination": pagination, "base_qs": base_qs,
        },
    )


@router.get("/talent/{seeker_user_id}", response_class=HTMLResponse)
async def talent_detail(request: Request, seeker_user_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        profile = conn.execute(
            "SELECT sp.*, u.name AS seeker_name, dt.name AS disability_name, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM seeker_profiles sp "
            "JOIN users u ON sp.user_id=u.id "
            "LEFT JOIN disability_types dt ON sp.disability_type_id=dt.id "
            "LEFT JOIN regions r ON sp.region_id=r.id "
            "WHERE sp.user_id=?",
            (seeker_user_id,),
        ).fetchone()
        if not profile:
            return RedirectResponse(url="/company/talents", status_code=303)

        certs = conn.execute(
            "SELECT * FROM seeker_certifications WHERE user_id=? ORDER BY cert_date DESC",
            (seeker_user_id,),
        ).fetchall()

        offered = bool(conn.execute(
            "SELECT 1 FROM talent_offers WHERE seeker_user_id=? AND company_user_id=?",
            (seeker_user_id, user["user_id"]),
        ).fetchone())

        company = conn.execute(
            "SELECT company_name FROM companies WHERE user_id=?", (user["user_id"],)
        ).fetchone()
    finally:
        conn.close()

    comm_pref = []
    assistive = []
    accommodation = []
    try:
        comm_pref = json.loads(profile["communication_pref"] or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        assistive = json.loads(profile["assistive_tech"] or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        accommodation = json.loads(profile["accommodation_needs"] or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    return templates.TemplateResponse(
        request=request,
        name="company/talent_detail.html",
        context={
            "request": request, "page_title": "인재 프로필",
            "user_name": user["user_name"], "user_role": "company",
            "profile": profile, "certs": certs,
            "offered": offered,
            "company_name": company["company_name"] if company else "",
            "comm_pref": comm_pref, "assistive": assistive,
            "accommodation": accommodation,
        },
    )


@api_router.post("/api/talent_offer/{seeker_user_id}")
async def send_talent_offer(
    request: Request,
    seeker_user_id: int,
    title: str = Form(...),
    message: str = Form(...),
    contact: str = Form(""),
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute(
            "SELECT company_name FROM companies WHERE user_id=?", (user["user_id"],)
        ).fetchone()
        company_name = company["company_name"] if company else ""
        conn.execute(
            "INSERT INTO talent_offers (seeker_user_id, company_user_id, company_name, title, message, contact) "
            "VALUES (?,?,?,?,?,?)",
            (seeker_user_id, user["user_id"], company_name, title, message, contact),
        )
        create_notification(
            conn, seeker_user_id,
            f"{company_name}에서 입사 제안을 보냈습니다",
            "/proposals",
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/company/talent/{seeker_user_id}?offered=1", status_code=303)
