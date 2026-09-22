import json
import time
from typing import Optional
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.notifications import create_notification
from core.security import verify_password

router = APIRouter(prefix="/company")
api_router = APIRouter()

TALENTS_AUTH_TTL = 1800  # 30분


def _talents_authed(request):
    ts = request.session.get("talents_authed_at")
    return ts and (time.time() - ts) < TALENTS_AUTH_TTL


@router.get("/talents/auth", response_class=HTMLResponse)
async def talents_auth_page(request: Request, next: Optional[str] = Query(None), error: str = ""):
    user = require_role(request, "company")
    return templates.TemplateResponse(
        request=request,
        name="company/talents_auth.html",
        context={
            "request": request, "page_title": "본인 확인",
            "user_name": user["name"], "user_role": "company",
            "error": error, "next_url": next or "",
        },
    )


@router.post("/talents/auth")
async def talents_auth_submit(
    request: Request,
    password: str = Form(...),
    next: str = Form(""),
):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT password FROM users WHERE id=?", (user["id"],)).fetchone()
    finally:
        conn.close()
    if row and verify_password(password, row["password"]):
        request.session["talents_authed_at"] = time.time()
        redirect_to = next if next and next.startswith("/company/talent") else "/company/talents"
        return RedirectResponse(url=redirect_to, status_code=303)
    return RedirectResponse(url="/company/talents/auth?error=wrong", status_code=303)


@router.get("/talents", response_class=HTMLResponse)
async def talent_search(
    request: Request,
    q: Optional[str] = Query(None),
    disability_type: Optional[str] = Query(None),
    region_id: Optional[int] = Query(None),
    sido: Optional[str] = Query(None),
    work_pref: Optional[str] = Query(None),
    edu: Optional[str] = Query(None),
    career_min: Optional[int] = Query(None),
    career_max: Optional[int] = Query(None),
    sort: Optional[str] = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "company")
    if not _talents_authed(request):
        return RedirectResponse(url="/company/talents/auth", status_code=303)
    conn = get_sqlite()
    try:
        company = conn.execute(
            "SELECT approval_status FROM companies WHERE user_id=?", (user["id"],)
        ).fetchone()
        if not company or company["approval_status"] != "approved":
            return templates.TemplateResponse(
                request=request,
                name="company/talents_blocked.html",
                context={
                    "request": request, "page_title": "인재 검색",
                    "user_name": user["name"], "user_role": "company",
                    "has_company": company is not None,
                    "status": company["approval_status"] if company else None,
                },
            )
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
        if edu:
            sql += " AND sp.education_level=?"
            params.append(edu)
        if career_min is not None:
            sql += " AND sp.career_years>=?"
            params.append(career_min)
        if career_max is not None:
            sql += " AND sp.career_years<=?"
            params.append(career_max)

        sort_map = {
            "career_desc": "sp.career_years DESC",
            "career_asc": "sp.career_years ASC",
        }
        order = sort_map.get(sort, "sp.updated_at DESC")
        sql += f" ORDER BY {order}"
        page = max(1, page)
        from core.pagination import page_info, PER_PAGE
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        pagination = page_info(total, page)
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        talents = conn.execute(sql, params).fetchall()

        company = conn.execute(
            "SELECT id FROM companies WHERE user_id=?", (user["id"],)
        ).fetchone()
        offered_ids = set()
        if company:
            rows = conn.execute(
                "SELECT seeker_user_id FROM talent_offers WHERE company_user_id=?",
                (user["id"],),
            ).fetchall()
            offered_ids = {r["seeker_user_id"] for r in rows}

        disability_types = conn.execute("SELECT * FROM disability_types ORDER BY id").fetchall()
    finally:
        conn.close()

    filtered = []
    for t in talents:
        t = dict(t)
        if t.get("disability_visibility") != "public":
            t["disability_name"] = None
            t["severity"] = None
        filtered.append(t)
    talents = filtered

    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if sido: qs_parts.append(f"sido={sido}")
    if disability_type: qs_parts.append(f"disability_type={disability_type}")
    if work_pref: qs_parts.append(f"work_pref={work_pref}")
    if edu: qs_parts.append(f"edu={edu}")
    if career_min is not None: qs_parts.append(f"career_min={career_min}")
    if career_max is not None: qs_parts.append(f"career_max={career_max}")
    if sort: qs_parts.append(f"sort={sort}")
    base_qs = "&".join(qs_parts)

    return templates.TemplateResponse(
        request=request,
        name="company/talents.html",
        context={
            "request": request, "page_title": "인재 검색",
            "user_name": user["name"], "user_role": "company",
            "talents": talents, "offered_ids": offered_ids,
            "disability_types": disability_types,
            "q": q or "", "selected_sido": sido or "",
            "selected_disability": disability_type or "",
            "selected_work_pref": work_pref or "",
            "selected_edu": edu or "",
            "selected_career_min": career_min if career_min is not None else "",
            "selected_career_max": career_max if career_max is not None else "",
            "selected_sort": sort or "",
            "pagination": pagination, "base_qs": base_qs,
        },
    )


@router.get("/talent/{seeker_user_id}", response_class=HTMLResponse)
async def talent_detail(request: Request, seeker_user_id: int, back: Optional[str] = Query(None)):
    user = require_role(request, "company")
    if not _talents_authed(request):
        return RedirectResponse(
            url=f"/company/talents/auth?next=/company/talent/{seeker_user_id}",
            status_code=303,
        )
    conn = get_sqlite()
    try:
        company_check = conn.execute(
            "SELECT approval_status FROM companies WHERE user_id=?", (user["id"],)
        ).fetchone()
        if not company_check or company_check["approval_status"] != "approved":
            return RedirectResponse(url="/company/talents", status_code=303)

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
            (seeker_user_id, user["id"]),
        ).fetchone())

        company = conn.execute(
            "SELECT company_name FROM companies WHERE user_id=?", (user["id"],)
        ).fetchone()

        conn.execute(
            "INSERT INTO access_log (viewer_id, seeker_user_id, purpose) VALUES (?,?,?)",
            (user["id"], seeker_user_id, "talent_search"),
        )
        create_notification(
            conn, seeker_user_id,
            f"{company['company_name']}에서 프로필을 열람했습니다.",
            "/profile/views",
        )
        conn.commit()
    finally:
        conn.close()

    disability_hidden = profile["disability_visibility"] != "public"
    if disability_hidden:
        profile = dict(profile)
        profile["disability_name"] = None
        profile["severity"] = None
        profile["disability_type_id"] = None

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
            "user_name": user["name"], "user_role": "company",
            "profile": profile, "certs": certs,
            "offered": offered, "disability_hidden": disability_hidden,
            "company_name": company["company_name"] if company else "",
            "comm_pref": comm_pref, "assistive": assistive,
            "accommodation": accommodation,
            "back_qs": back or "",
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
            "SELECT company_name FROM companies WHERE user_id=?", (user["id"],)
        ).fetchone()
        company_name = company["company_name"] if company else ""
        conn.execute(
            "INSERT INTO talent_offers (seeker_user_id, company_user_id, company_name, title, message, contact) "
            "VALUES (?,?,?,?,?,?)",
            (seeker_user_id, user["id"], company_name, title, message, contact),
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
