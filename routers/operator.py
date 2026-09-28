from core.security import hash_password, MIN_PASSWORD_LENGTH
import json
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import PURPOSE_LABELS, EMPLOYMENT_TYPES, COMPANY_SIZES, INDUSTRY_TYPES
from core.pagination import page_info, PER_PAGE
from core.notifications import create_notification

router = APIRouter(prefix="/op")



@router.get("/seekers", response_class=HTMLResponse)
async def op_seekers(
    request: Request,
    q: str = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT u.id, u.name, u.username, u.created_at, u.is_deleted, "
            "mgr.name AS manager_name "
            "FROM users u "
            "LEFT JOIN manager_assignments ma ON u.id = ma.seeker_user_id "
            "LEFT JOIN users mgr ON ma.manager_user_id = mgr.id "
            "WHERE u.role = 'seeker'"
        )
        params = []
        if q:
            sql += " AND (u.name LIKE ? OR u.username LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
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
    return templates.TemplateResponse(
        request=request, name="op/seekers.html", context={
            "request": request, "page_title": "구직자 목록",
            "user_name": user["name"], "user_role": "operator",
            "seekers": seekers,
            "q": q or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )



@router.post("/seekers/{seeker_id}/assign-manager")
async def op_assign_manager(
    request: Request,
    seeker_id: int,
    manager_id: int = Form(...),
):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        mgr = conn.execute("SELECT id FROM users WHERE id=? AND role='manager'", (manager_id,)).fetchone()
        if not mgr:
            raise HTTPException(status_code=400, detail="유효하지 않은 매니저입니다.")
        conn.execute(
            "INSERT OR REPLACE INTO manager_assignments (manager_user_id, seeker_user_id, assigned_by) VALUES (?,?,?)",
            (manager_id, seeker_id, request.session.get("id")),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/seekers/{seeker_id}", status_code=303)


@router.get("/managers", response_class=HTMLResponse)
async def op_managers(request: Request, q: str = Query(None), page: int = Query(1)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = """SELECT u.id, u.username, u.name, u.phone, u.created_at, u.is_deleted,
                        COUNT(DISTINCT ma.seeker_user_id) AS assigned_count
                 FROM users u
                 LEFT JOIN manager_assignments ma ON u.id = ma.manager_user_id
                 WHERE u.role='manager'"""
        params = []
        if q and q.strip():
            sql += " AND (u.name LIKE ? OR u.username LIKE ?)"
            params += [f"%{q.strip()}%", f"%{q.strip()}%"]
        sql += " GROUP BY u.id ORDER BY u.is_deleted ASC, u.created_at DESC"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        managers = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    return templates.TemplateResponse(
        request=request, name="op/managers.html", context={
            "request": request, "page_title": "상담사 관리",
            "user_name": user["name"], "user_role": "operator",
            "managers": managers,
            "q": q or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/managers/check-duplicate")
async def op_check_duplicate(
    request: Request,
    field: str = Query("username"),
    value: str = Query(""),
):
    require_role(request, "operator")
    val = value.strip()
    if not val or field not in ("username", "email"):
        return JSONResponse({"available": False})
    conn = get_sqlite()
    try:
        exists = conn.execute(f"SELECT 1 FROM users WHERE {field}=?", (val,)).fetchone()
    finally:
        conn.close()
    return JSONResponse({"available": not exists})


@router.post("/managers/create")
async def op_create_manager(
    request: Request,
    username: str = Form(...),
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    password: str = Form(...),
):
    require_role(request, "operator")
    if len(password) < MIN_PASSWORD_LENGTH:
        return RedirectResponse(url="/op/managers?error=short_pw", status_code=303)
    conn = get_sqlite()
    try:
        exists = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
        if exists:
            return RedirectResponse(url="/op/managers?error=dup_id", status_code=303)
        if email and conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            return RedirectResponse(url="/op/managers?error=dup_email", status_code=303)
        hashed = hash_password(password)
        conn.execute(
            "INSERT INTO users (username, password, name, phone, email, role, must_change_password) VALUES (?,?,?,?,?,?,1)",
            (username, hashed, name, phone, email, "manager"),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/managers?msg=created&new_user={quote(username)}&new_pw={quote(password)}", status_code=303)


@router.get("/managers/{manager_id}/assigned-count")
async def op_manager_assigned_count(request: Request, manager_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM manager_assignments WHERE manager_user_id=?",
            (manager_id,),
        ).fetchone()[0]
        others = conn.execute(
            "SELECT id, name FROM users WHERE role='manager' AND is_deleted=0 AND id != ?",
            (manager_id,),
        ).fetchall()
    finally:
        conn.close()
    return JSONResponse({
        "count": cnt,
        "managers": [{"id": m["id"], "name": m["name"]} for m in others],
    })


@router.post("/managers/{manager_id}/toggle")
async def op_toggle_manager(request: Request, manager_id: int):
    require_role(request, "operator")
    form = await request.form()
    transfer_to = form.get("transfer_to", "")
    transfer_to = int(transfer_to) if transfer_to else 0
    conn = get_sqlite()
    try:
        mgr = conn.execute(
            "SELECT id, is_deleted, name FROM users WHERE id=? AND role='manager'", (manager_id,)
        ).fetchone()
        if not mgr:
            raise HTTPException(status_code=404, detail="상담사를 찾을 수 없습니다.")
        new_val = 0 if mgr["is_deleted"] else 1
        conn.execute("UPDATE users SET is_deleted=? WHERE id=?", (new_val, manager_id))

        # 비활성화 시 담당 구직자 이관
        if new_val == 1:
            seekers = conn.execute(
                "SELECT seeker_user_id FROM manager_assignments WHERE manager_user_id=?",
                (manager_id,),
            ).fetchall()
            op_id = request.session.get("id")

            if transfer_to:
                new_mgr = conn.execute(
                    "SELECT name FROM users WHERE id=? AND role='manager' AND is_deleted=0",
                    (transfer_to,),
                ).fetchone()
                new_mgr_name = new_mgr["name"] if new_mgr else ""
                conn.execute(
                    "UPDATE manager_assignments SET manager_user_id=?, assigned_by=? WHERE manager_user_id=?",
                    (transfer_to, op_id, manager_id),
                )
            else:
                new_mgr_name = ""
                conn.execute(
                    "DELETE FROM manager_assignments WHERE manager_user_id=?",
                    (manager_id,),
                )

            for s in seekers:
                sid = s["seeker_user_id"]
                conn.execute(
                    "INSERT INTO manager_reassignment_log (seeker_user_id, from_manager_id, to_manager_id, reason, reassigned_by) VALUES (?,?,?,?,?)",
                    (sid, manager_id, transfer_to or None, "매니저 비활성화", op_id),
                )
                if transfer_to:
                    msg = f"담당 매니저가 {new_mgr_name}(으)로 변경되었습니다."
                else:
                    msg = "담당 매니저가 변경되었습니다. 새 매니저가 배정되면 안내드리겠습니다."
                create_notification(conn, sid, msg)

        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/op/managers", status_code=303)


@router.post("/managers/{manager_id}/reset-password")
async def op_reset_manager_pw(request: Request, manager_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        mgr = conn.execute(
            "SELECT id, name FROM users WHERE id=? AND role='manager'", (manager_id,)
        ).fetchone()
        if not mgr:
            raise HTTPException(status_code=404, detail="상담사를 찾을 수 없습니다.")
        temp_pw = secrets.token_urlsafe(8)
        conn.execute(
            "UPDATE users SET password=?, must_change_password=1 WHERE id=?",
            (hash_password(temp_pw), manager_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(
        url=f"/op/managers?msg=pw_reset&temp_pw={quote(temp_pw)}&target_name={quote(mgr['name'])}",
        status_code=303,
    )


@router.get("/companies", response_class=HTMLResponse)
async def op_companies(
    request: Request,
    q: str = Query(None),
    industry: str = Query(None),
    company_size: str = Query(None),
    sido: str = Query(None),
    hiring_experience: str = Query(None),
    approval: str = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT c.*, u.name AS owner_name, u.username, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu "
            "FROM companies c "
            "JOIN users u ON c.user_id = u.id "
            "LEFT JOIN regions r ON c.region_id = r.id "
            "WHERE 1=1"
        )
        params = []
        if q:
            sql += " AND (c.company_name LIKE ? OR c.biz_no LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if industry:
            sql += " AND c.industry=?"
            params.append(industry)
        if company_size:
            sql += " AND c.company_size=?"
            params.append(company_size)
        if sido:
            sql += " AND r.sido=?"
            params.append(sido)
        if hiring_experience == "1":
            sql += " AND c.hiring_experience=1"
        elif hiring_experience == "0":
            sql += " AND (c.hiring_experience=0 OR c.hiring_experience IS NULL)"
        if approval in ("pending", "approved", "rejected"):
            sql += " AND c.approval_status=?"
            params.append(approval)
        sql += " ORDER BY c.id"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        rows = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    companies = []
    for row in rows:
        d = dict(row)
        fac = d.get("accessibility_facilities") or "[]"
        try:
            d["facility_count"] = len(json.loads(fac))
        except (json.JSONDecodeError, TypeError):
            d["facility_count"] = 0
        companies.append(d)
    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if industry: qs_parts.append(f"industry={industry}")
    if company_size: qs_parts.append(f"company_size={company_size}")
    if sido: qs_parts.append(f"sido={sido}")
    if hiring_experience: qs_parts.append(f"hiring_experience={hiring_experience}")
    if approval: qs_parts.append(f"approval={approval}")
    return templates.TemplateResponse(
        request=request, name="op/companies.html", context={
            "request": request, "page_title": "기업 목록",
            "user_name": user["name"], "user_role": "operator",
            "companies": companies,
            "company_sizes": COMPANY_SIZES,
            "industry_types": INDUSTRY_TYPES,
            "q": q or "",
            "selected_industry": industry or "",
            "selected_size": company_size or "",
            "selected_sido": sido or "",
            "selected_hiring": hiring_experience or "",
            "selected_approval": approval or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/companies/{company_id}", response_class=HTMLResponse)
async def op_company_detail(request: Request, company_id: int):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        company = conn.execute(
            """SELECT c.*, r.sido AS region_sido, r.sigungu AS region_sigungu,
                      u.name AS account_name, u.phone AS account_phone, u.username AS account_email
               FROM companies c
               LEFT JOIN regions r ON c.region_id = r.id
               LEFT JOIN users u ON c.user_id = u.id
               WHERE c.id = ?""",
            (company_id,),
        ).fetchone()
        if company is None:
            raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다.")
        active_jobs = conn.execute(
            "SELECT COUNT(*) FROM job_postings WHERE company_id=? AND status='open'", (company_id,)
        ).fetchone()[0]
        placed_count = conn.execute(
            "SELECT COUNT(*) FROM placements WHERE company_id=? AND end_date IS NULL", (company_id,)
        ).fetchone()[0]
        reviews = conn.execute(
            "SELECT id, rating, pros, cons, created_at FROM company_reviews WHERE company_id=? ORDER BY created_at DESC",
            (company_id,),
        ).fetchall()
        avg_rating = round(sum(r["rating"] for r in reviews) / len(reviews), 1) if reviews else None
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/company_detail.html", context={
            "request": request, "page_title": f"기업 상세 - {company['company_name']}",
            "user_name": user["name"], "user_role": "operator",
            "company": company,
            "active_jobs": active_jobs,
            "placed_count": placed_count,
            "reviews": reviews,
            "avg_rating": avg_rating,
        }
    )


@router.post("/companies/{company_id}/approve")
async def op_company_approve(request: Request, company_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute("UPDATE companies SET approval_status='approved', rejection_reason='', reverify=0 WHERE id=?", (company_id,))
        company = conn.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)).fetchone()
        if company:
            create_notification(conn, company["user_id"], "사업자 인증이 승인되었습니다.", "/company/profile")
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/companies/{company_id}", status_code=303)


@router.post("/companies/{company_id}/reject")
async def op_company_reject(request: Request, company_id: int):
    require_role(request, "operator")
    form = await request.form()
    reason = form.get("rejection_reason", "")
    conn = get_sqlite()
    try:
        conn.execute("UPDATE companies SET approval_status='rejected', rejection_reason=?, reverify=0 WHERE id=?", (reason, company_id))
        company = conn.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)).fetchone()
        if company:
            create_notification(conn, company["user_id"], "사업자 인증이 반려되었습니다. 사유를 확인해 주세요.", "/company/profile")
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/companies/{company_id}", status_code=303)


@router.post("/companies/{company_id}/reviews/{review_id}/delete")
async def op_delete_review(request: Request, company_id: int, review_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute(
            "DELETE FROM company_reviews WHERE id=? AND company_id=?",
            (review_id, company_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/companies/{company_id}", status_code=303)


@router.get("/jobs", response_class=HTMLResponse)
async def op_jobs(
    request: Request,
    q: str = Query(None),
    status: str = Query(None),
    sido: str = Query(None),
    employment_type: str = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT jp.*, c.company_name, "
            "r.sido AS region_sido, r.sigungu AS region_sigungu, "
            "(SELECT COUNT(*) FROM candidacies ca WHERE ca.job_id=jp.id) AS applicant_count "
            "FROM job_postings jp "
            "JOIN companies c ON jp.company_id = c.id "
            "LEFT JOIN regions r ON jp.region_id = r.id "
            "WHERE 1=1"
        )
        params = []
        if q:
            sql += " AND (jp.title LIKE ? OR jp.description LIKE ? OR c.company_name LIKE ?)"
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        if status:
            sql += " AND jp.status=?"
            params.append(status)
        if sido:
            sql += " AND r.sido=?"
            params.append(sido)
        if employment_type:
            sql += " AND jp.employment_type=?"
            params.append(employment_type)
        sql += " ORDER BY jp.created_at DESC"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        jobs = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    qs_parts = []
    if q: qs_parts.append(f"q={q}")
    if status: qs_parts.append(f"status={status}")
    if sido: qs_parts.append(f"sido={sido}")
    if employment_type: qs_parts.append(f"employment_type={employment_type}")
    return templates.TemplateResponse(
        request=request, name="op/jobs.html", context={
            "request": request, "page_title": "전체 공고",
            "user_name": user["name"], "user_role": "operator",
            "jobs": jobs,
            "employment_types": EMPLOYMENT_TYPES,
            "q": q or "",
            "selected_status": status or "",
            "selected_sido": sido or "",
            "selected_type": employment_type or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def op_job_detail(request: Request, job_id: int):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        job = conn.execute(
            """SELECT jp.*, c.company_name, jc.minor_name_ko AS category_name,
                      jc.fit_physical_lower, jc.fit_physical_upper,
                      jc.fit_hearing, jc.fit_visual_low,
                      jc.fit_intellectual, jc.fit_autism,
                      jc.fit_mental, jc.fit_internal_organ,
                      jc.fit_brain_lesion, jc.fit_notes,
                      r.sido AS region_sido, r.sigungu AS region_sigungu
               FROM job_postings jp
               JOIN companies c ON jp.company_id = c.id
               LEFT JOIN job_categories jc ON jp.category_id = jc.id
               LEFT JOIN regions r ON jp.region_id = r.id
               WHERE jp.id = ?""",
            (job_id,),
        ).fetchone()
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM candidacies WHERE job_id=? GROUP BY status",
            (job_id,),
        ).fetchall()
    finally:
        conn.close()
    if not job:
        return RedirectResponse(url="/op/jobs", status_code=303)
    _labels = {
        "pending": "접수", "reviewing": "검토중", "shortlisted": "서류합격",
        "interview": "면접", "offer": "제의", "hired": "채용",
        "rejected": "불합격", "withdrawn": "지원취소",
    }
    status_breakdown = [(_labels.get(r["status"], r["status"]), r["cnt"]) for r in status_rows]
    total_applicants = sum(r["cnt"] for r in status_rows)
    accommodations = json.loads(job["accommodations_provided"]) if job["accommodations_provided"] else []
    return templates.TemplateResponse(
        request=request, name="op/job_detail.html", context={
            "request": request, "page_title": job["title"],
            "user_name": user["name"], "user_role": "operator",
            "job": job,
            "accommodations": accommodations,
            "status_breakdown": status_breakdown,
            "total_applicants": total_applicants,
        }
    )



@router.post("/jobs/{job_id}/approve")
async def op_job_approve(request: Request, job_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE job_postings SET status='open', rejection_reason='' WHERE id=?",
            (job_id,),
        )
        job = conn.execute(
            "SELECT jp.title, c.user_id FROM job_postings jp JOIN companies c ON jp.company_id=c.id WHERE jp.id=?",
            (job_id,),
        ).fetchone()
        if job:
            create_notification(
                conn, job["user_id"],
                f"[{job['title']}] 공고가 승인되어 게시되었습니다.",
                "/company/jobs",
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/reject")
async def op_job_reject(request: Request, job_id: int):
    require_role(request, "operator")
    form = await request.form()
    reason = form.get("rejection_reason", "")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE job_postings SET status='rejected', rejection_reason=? WHERE id=?",
            (reason, job_id),
        )
        job = conn.execute(
            "SELECT jp.title, c.user_id FROM job_postings jp JOIN companies c ON jp.company_id=c.id WHERE jp.id=?",
            (job_id,),
        ).fetchone()
        if job:
            create_notification(
                conn, job["user_id"],
                f"[{job['title']}] 공고가 반려되었습니다. 사유를 확인해 주세요.",
                "/company/jobs",
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/jobs/{job_id}", status_code=303)







@router.post("/users/{target_user_id}/reset-password")
async def op_reset_password(
    request: Request,
    target_user_id: int,
    new_password: str = Form(...),
):
    user = require_role(request, "operator")
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return RedirectResponse(url=f"/op/seekers/{target_user_id}", status_code=303)
    hashed = hash_password(new_password)
    conn = get_sqlite()
    try:
        target = conn.execute("SELECT id, role FROM users WHERE id=?", (target_user_id,)).fetchone()
        if target:
            conn.execute("UPDATE users SET password=? WHERE id=?", (hashed, target_user_id))
            conn.commit()
    finally:
        conn.close()
    referer = request.headers.get("referer", "/op/seekers")
    return RedirectResponse(url=referer, status_code=303)







INQUIRY_STATUS = {"open": "미답변", "answered": "답변완료", "closed": "종료"}


@router.get("/inquiries", response_class=HTMLResponse)
async def op_inquiries(
    request: Request,
    status: str = Query(None),
    page: int = Query(1),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        sql = (
            "SELECT i.*, u.name AS user_name, u.role AS user_role "
            "FROM inquiries i JOIN users u ON i.user_id=u.id"
        )
        params = []
        if status in ("open", "answered", "closed"):
            sql += " WHERE i.status=?"
            params.append(status)
        sql += " ORDER BY CASE i.status WHEN 'open' THEN 0 WHEN 'answered' THEN 1 ELSE 2 END, i.created_at DESC"
        page = max(1, page)
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        rows = conn.execute(sql, params).fetchall()
        pagination = page_info(total, page)
    finally:
        conn.close()
    qs_parts = []
    if status: qs_parts.append(f"status={status}")
    return templates.TemplateResponse(
        request=request, name="op/inquiries.html", context={
            "request": request, "page_title": "문의 관리",
            "user_name": user["name"], "user_role": "operator",
            "inquiries": rows,
            "status_labels": INQUIRY_STATUS,
            "selected_status": status or "",
            "pagination": pagination, "base_qs": "&".join(qs_parts),
        }
    )


@router.get("/inquiries/{inquiry_id}", response_class=HTMLResponse)
async def op_inquiry_detail(request: Request, inquiry_id: int):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT i.*, u.name AS user_name, u.role AS user_role, u.username "
            "FROM inquiries i JOIN users u ON i.user_id=u.id WHERE i.id=?",
            (inquiry_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return RedirectResponse(url="/op/inquiries", status_code=303)
    return templates.TemplateResponse(
        request=request, name="op/inquiry_detail.html", context={
            "request": request, "page_title": f"문의 #{inquiry_id}",
            "user_name": user["name"], "user_role": "operator",
            "inquiry": row,
            "status_labels": INQUIRY_STATUS,
        }
    )


@router.post("/inquiries/{inquiry_id}/answer")
async def op_inquiry_answer(
    request: Request,
    inquiry_id: int,
    answer: str = Form(...),
):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE inquiries SET answer=?, answered_by=?, answered_at=datetime('now','localtime'), status='answered' WHERE id=?",
            (answer.strip(), user["id"], inquiry_id),
        )
        inq = conn.execute("SELECT user_id, subject FROM inquiries WHERE id=?", (inquiry_id,)).fetchone()
        if inq:
            create_notification(
                conn, inq["user_id"],
                f"[{inq['subject']}] 문의에 답변이 등록되었습니다.",
                f"/inquiries/{inquiry_id}",
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/inquiries/{inquiry_id}", status_code=303)


@router.post("/inquiries/{inquiry_id}/close")
async def op_inquiry_close(request: Request, inquiry_id: int):
    require_role(request, "operator")
    conn = get_sqlite()
    try:
        conn.execute("UPDATE inquiries SET status='closed' WHERE id=?", (inquiry_id,))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/inquiries/{inquiry_id}", status_code=303)


@router.get("/access-log", response_class=HTMLResponse)
async def op_access_log(request: Request, page: int = Query(1)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        total = conn.execute("SELECT COUNT(*) FROM access_log").fetchone()[0]
        pagination = page_info(total, page)
        logs = conn.execute(
            """SELECT al.*,
                      v.name AS viewer_name, v.role AS viewer_role,
                      s.name AS seeker_name
               FROM access_log al
               JOIN users v ON al.viewer_id = v.id
               JOIN users s ON al.seeker_user_id = s.id
               ORDER BY al.created_at DESC
               LIMIT ? OFFSET ?""",
            (pagination["per_page"], (pagination["page"] - 1) * pagination["per_page"]),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/access_log.html", context={
            "request": request, "page_title": "열람 기록",
            "user_name": user["name"], "user_role": "operator",
            "logs": logs,
            "pagination": pagination,
            "purpose_labels": PURPOSE_LABELS,
            "base_qs": "",
        }
    )
