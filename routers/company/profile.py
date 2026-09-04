import json
from typing import Optional
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import COMPANY_SIZES, INDUSTRY_TYPES, ACCOMMODATION_OPTIONS
from core.upload import save_upload

router = APIRouter(prefix="/company")


@router.get("/profile", response_class=HTMLResponse)
async def company_profile_form(request: Request, success: str = ""):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        selected_sido = ""
        accessibility_facilities = []
        if company:
            if company["region_id"]:
                region_row = conn.execute("SELECT sido FROM regions WHERE id=?", (company["region_id"],)).fetchone()
                if region_row:
                    selected_sido = region_row["sido"]
            if company["accessibility_facilities"]:
                accessibility_facilities = json.loads(company["accessibility_facilities"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/profile_form.html", context={
            "request": request, "page_title": "기업 정보",
            "user_name": user["user_name"], "user_role": "company",
            "company": company, "success": success,
            "selected_sido": selected_sido,
            "company_sizes": COMPANY_SIZES,
            "industry_types": INDUSTRY_TYPES,
            "accommodation_options": ACCOMMODATION_OPTIONS,
            "accessibility_facilities": accessibility_facilities,
        }
    )


@router.post("/profile")
async def company_profile_save(
    request: Request,
    company_name: str = Form(...),
    biz_no: str = Form(""),
    industry: str = Form(""),
    employee_count: int = Form(0),
    disabled_count: int = Form(0),
    region_id: int = Form(None),
    intro: str = Form(""),
    website: str = Form(""),
    company_size: str = Form(""),
    accessibility_note: str = Form(""),
    hiring_experience: str = Form("0"),
    retention_note: str = Form(""),
    benefits: str = Form(""),
    logo: Optional[UploadFile] = File(None),
):
    user = require_role(request, "company")
    form = await request.form()
    hiring_exp_val = 1 if hiring_experience in ("1", "on", "true") else 0
    accessibility_facilities = json.dumps(form.getlist("accessibility_facilities"), ensure_ascii=False)

    logo_path = ""
    if logo and logo.filename:
        logo_path = await save_upload(
            logo, "logos", user["user_id"],
            ["image/jpeg", "image/png", "image/webp"], 5 * 1024 * 1024,
        )

    conn = get_sqlite()
    try:
        existing = conn.execute("SELECT id, logo_path FROM companies WHERE user_id=?", (user["user_id"],)).fetchone()
        if not logo_path and existing:
            logo_path = existing["logo_path"] or ""
        if existing:
            conn.execute("""UPDATE companies SET
                company_name=?, biz_no=?, industry=?, employee_count=?, disabled_count=?,
                region_id=?, intro=?, website=?, company_size=?,
                accessibility_facilities=?, accessibility_note=?,
                hiring_experience=?, retention_note=?, benefits=?, logo_path=?,
                updated_at=datetime('now','localtime')
                WHERE user_id=?""",
                (company_name, biz_no, industry, employee_count, disabled_count,
                 region_id, intro, website, company_size,
                 accessibility_facilities, accessibility_note,
                 hiring_exp_val, retention_note, benefits, logo_path,
                 user["user_id"]))
        else:
            conn.execute("""INSERT INTO companies
                (user_id, company_name, biz_no, industry, employee_count, disabled_count,
                 region_id, intro, website, company_size,
                 accessibility_facilities, accessibility_note,
                 hiring_experience, retention_note, benefits, logo_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (user["user_id"], company_name, biz_no, industry, employee_count, disabled_count,
                 region_id, intro, website, company_size,
                 accessibility_facilities, accessibility_note,
                 hiring_exp_val, retention_note, benefits, logo_path))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/profile?success=1", status_code=303)
