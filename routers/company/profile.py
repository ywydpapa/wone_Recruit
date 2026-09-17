import json
from typing import Optional
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import COMPANY_SIZES, INDUSTRY_TYPES, ACCOMMODATION_OPTIONS
from core.upload import save_upload

router = APIRouter(prefix="/company")

BENEFIT_OPTIONS = [
    "4대보험", "점심제공", "교통비지원", "장애인편의시설", "보조기기지원",
    "유연근무", "재택근무", "연차보장", "경조사지원", "자기개발지원",
]


@router.get("/profile", response_class=HTMLResponse)
async def company_profile_form(request: Request, success: str = ""):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["id"],)).fetchone()
        selected_sido = ""
        accessibility_facilities = []
        selected_benefits = []
        photos = []
        if company:
            if company["region_id"]:
                region_row = conn.execute("SELECT sido FROM regions WHERE id=?", (company["region_id"],)).fetchone()
                if region_row:
                    selected_sido = region_row["sido"]
            if company["accessibility_facilities"]:
                accessibility_facilities = json.loads(company["accessibility_facilities"])
            if company["benefits"]:
                try:
                    parsed = json.loads(company["benefits"])
                    # JSON 배열이면 체크박스 선택값, 아니면 레거시 텍스트
                    if isinstance(parsed, list):
                        selected_benefits = parsed
                except (json.JSONDecodeError, ValueError):
                    pass
            photos = conn.execute(
                "SELECT * FROM company_photos WHERE company_id=? ORDER BY sort_order, id",
                (company["id"],)
            ).fetchall()
    finally:
        conn.close()
    approval_status = company["approval_status"] if company else "pending"
    return templates.TemplateResponse(
        request=request, name="company/profile_form.html", context={
            "request": request, "page_title": "기업 정보",
            "user_name": user["name"], "user_role": "company",
            "company": company, "success": success,
            "selected_sido": selected_sido,
            "company_sizes": COMPANY_SIZES,
            "industry_types": INDUSTRY_TYPES,
            "accommodation_options": ACCOMMODATION_OPTIONS,
            "accessibility_facilities": accessibility_facilities,
            "approval_status": approval_status,
            "benefit_options": BENEFIT_OPTIONS,
            "selected_benefits": selected_benefits,
            "photos": photos,
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
    ceo: str = Form(""),
    est_year: int = Form(None),
    biz_type: str = Form(""),
    address: str = Form(""),
    contact_phone: str = Form(""),
    contact_email: str = Form(""),
    hr_name: str = Form(""),
    hr_position: str = Form(""),
    hr_phone: str = Form(""),
    hr_email: str = Form(""),
    tagline: str = Form(""),
    description: str = Form(""),
    logo: Optional[UploadFile] = File(None),
    biz_doc: Optional[UploadFile] = File(None),
):
    user = require_role(request, "company")
    form = await request.form()
    hiring_exp_val = 1 if hiring_experience in ("1", "on", "true") else 0
    accessibility_facilities = json.dumps(form.getlist("accessibility_facilities"), ensure_ascii=False)
    selected_benefits = json.dumps(form.getlist("benefits"), ensure_ascii=False)
    photos = form.getlist("photos")

    tagline = tagline[:20]

    logo_path = ""
    if logo and logo.filename:
        logo_path = await save_upload(
            logo, "logos", user["id"],
            ["image/jpeg", "image/png", "image/webp"], 5 * 1024 * 1024,
        )

    biz_doc_path = ""
    if biz_doc and biz_doc.filename:
        biz_doc_path = await save_upload(
            biz_doc, "biz_docs", user["id"],
            ["application/pdf", "image/jpeg", "image/png"], 10 * 1024 * 1024,
        )

    conn = get_sqlite()
    try:
        existing = conn.execute("SELECT id, logo_path, biz_doc_path FROM companies WHERE user_id=?", (user["id"],)).fetchone()
        if not logo_path and existing:
            logo_path = existing["logo_path"] or ""
        if not biz_doc_path and existing:
            biz_doc_path = existing["biz_doc_path"] or ""
        est_year_val = est_year if est_year else None
        if existing:
            conn.execute("""UPDATE companies SET
                company_name=?, biz_no=?, industry=?, employee_count=?, disabled_count=?,
                region_id=?, intro=?, website=?, company_size=?,
                accessibility_facilities=?, accessibility_note=?,
                hiring_experience=?, retention_note=?, benefits=?, logo_path=?,
                ceo=?, est_year=?, biz_type=?, address=?, biz_doc_path=?,
                contact_phone=?, contact_email=?,
                hr_name=?, hr_position=?, hr_phone=?, hr_email=?,
                tagline=?, description=?,
                updated_at=datetime('now','localtime')
                WHERE user_id=?""",
                (company_name, biz_no, industry, employee_count, disabled_count,
                 region_id, intro, website, company_size,
                 accessibility_facilities, accessibility_note,
                 hiring_exp_val, retention_note, selected_benefits, logo_path,
                 ceo, est_year_val, biz_type, address, biz_doc_path,
                 contact_phone, contact_email,
                 hr_name, hr_position, hr_phone, hr_email,
                 tagline, description,
                 user["id"]))
            company_id = existing["id"]
        else:
            cur = conn.execute("""INSERT INTO companies
                (user_id, company_name, biz_no, industry, employee_count, disabled_count,
                 region_id, intro, website, company_size,
                 accessibility_facilities, accessibility_note,
                 hiring_experience, retention_note, benefits, logo_path,
                 ceo, est_year, biz_type, address, biz_doc_path,
                 contact_phone, contact_email,
                 hr_name, hr_position, hr_phone, hr_email,
                 tagline, description)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (user["id"], company_name, biz_no, industry, employee_count, disabled_count,
                 region_id, intro, website, company_size,
                 accessibility_facilities, accessibility_note,
                 hiring_exp_val, retention_note, selected_benefits, logo_path,
                 ceo, est_year_val, biz_type, address, biz_doc_path,
                 contact_phone, contact_email,
                 hr_name, hr_position, hr_phone, hr_email,
                 tagline, description))
            company_id = cur.lastrowid

        # 사진 삭제 처리
        delete_ids = form.getlist("delete_photo")
        if delete_ids:
            for pid in delete_ids:
                conn.execute("DELETE FROM company_photos WHERE id=? AND company_id=?", (pid, company_id))

        # 삭제 반영 후 현재 장수 확인
        current_count = conn.execute(
            "SELECT COUNT(*) FROM company_photos WHERE company_id=?", (company_id,)
        ).fetchone()[0]
        captions = form.getlist("photo_caption")
        uploaded = 0
        for idx, photo in enumerate(photos):
            if not photo or not photo.filename:
                continue
            if current_count + uploaded >= 4:
                break
            path = await save_upload(
                photo, "company_photos", company_id,
                ["image/jpeg", "image/png", "image/webp"], 5 * 1024 * 1024,
            )
            if path:
                caption = captions[idx] if idx < len(captions) else ""
                conn.execute(
                    "INSERT INTO company_photos (company_id, file_path, caption, sort_order) VALUES (?,?,?,?)",
                    (company_id, path, caption, current_count + uploaded),
                )
                uploaded += 1

        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/profile?success=1", status_code=303)
