import json
import secrets
import sqlite3

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from core.constants import PURPOSE_LABELS
from core.db import get_sqlite
from core.deps import check_login, require_role, templates
from core.rate_limit import check_login_rate, record_login_attempt, clear_login_attempts, get_client_ip
from core.security import hash_password, verify_password, MIN_PASSWORD_LENGTH

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if check_login(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/login/login.html", context={
            "request": request, "page_title": "로그인", "error": error,
        }
    )


@router.post("/login_check")
async def login_check(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = get_client_ip(request)
    if check_login_rate(ip):
        return RedirectResponse(url="/login?error=rate_limit", status_code=303)
    record_login_attempt(ip)
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
    finally:
        conn.close()
    if row and verify_password(password, row["password"]):
        if row["is_deleted"]:
            return RedirectResponse(url="/login?error=deleted", status_code=303)
        clear_login_attempts(ip)
        request.session.pop("csrf_token", None)
        request.session["logined"] = True
        request.session["id"] = row["id"]
        request.session["username"] = row["username"]
        request.session["name"] = row["name"]
        request.session["role"] = row["role"]
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request, error: str = ""):
    if check_login(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request, name="login/forgot_password.html", context={
            "request": request, "page_title": "비밀번호 찾기",
            "error": error, "temp_pw": "",
        }
    )


@router.post("/forgot-password")
async def forgot_password_submit(
    request: Request,
    username: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
):
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT id, is_deleted FROM users WHERE username=? AND name=? AND phone=?",
            (username, name, phone),
        ).fetchone()
        if not row:
            return RedirectResponse(url="/forgot-password?error=not_found", status_code=303)
        if row["is_deleted"]:
            return RedirectResponse(url="/forgot-password?error=deleted", status_code=303)
        temp_pw = secrets.token_urlsafe(8)
        conn.execute("UPDATE users SET password=? WHERE id=?", (hash_password(temp_pw), row["id"]))
        conn.commit()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="login/forgot_password.html", context={
            "request": request, "page_title": "비밀번호 찾기",
            "error": "", "temp_pw": temp_pw,
        }
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request, error: str = ""):
    return templates.TemplateResponse(
        request=request, name="/login/signup.html", context={
            "request": request, "page_title": "회원가입", "error": error,
        }
    )


@router.post("/signup")
async def signup_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    role: str = Form("seeker"),
    agree_terms: str = Form(""),
    agree_privacy: str = Form(""),
    agree_marketing: str = Form(""),
):
    if role not in ("seeker", "company"):
        return RedirectResponse(url="/signup?error=invalid_role", status_code=303)
    if not agree_terms or not agree_privacy:
        return RedirectResponse(url="/signup?error=agree_required", status_code=303)
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    marketing_at = now if agree_marketing else None
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO users (username, password, name, phone, email, role, agreed_terms_at, agreed_privacy_at, agreed_marketing_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (username, hash_password(password), name, phone, email, role, now, now, marketing_at)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return RedirectResponse(url="/signup?error=dup", status_code=303)
    finally:
        conn.close()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/account/mypage", response_class=HTMLResponse)
async def mypage(request: Request):
    user = require_role(request, "seeker", "company", "operator", "manager")
    return templates.TemplateResponse(
        request=request, name="account/mypage.html", context={
            "request": request, "page_title": "마이페이지",
            "user_name": user.get("name", ""),
            "user_role": user.get("role", "seeker"),
        }
    )


@router.get("/account/password", response_class=HTMLResponse)
async def password_change_form(request: Request, error: str = "", success: str = ""):
    require_role(request, "seeker", "company", "operator", "manager")
    user = request.session
    return templates.TemplateResponse(
        request=request, name="account/password.html", context={
            "request": request, "page_title": "비밀번호 변경",
            "user_name": user.get("name", ""),
            "user_role": user.get("role", "seeker"),
            "error": error, "success": success,
        }
    )


@router.post("/account/password")
async def password_change_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    user = require_role(request, "seeker", "company", "operator", "manager")
    if new_password != confirm_password:
        return RedirectResponse(url="/account/password?error=mismatch", status_code=303)
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return RedirectResponse(url="/account/password?error=short", status_code=303)
    if current_password == new_password:
        return RedirectResponse(url="/account/password?error=same", status_code=303)
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT id, password FROM users WHERE id=?", (user["id"],)
        ).fetchone()
        if not row or not verify_password(current_password, row["password"]):
            return RedirectResponse(url="/account/password?error=wrong", status_code=303)
        conn.execute("UPDATE users SET password=? WHERE id=?", (hash_password(new_password), user["id"]))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/account/password?success=1", status_code=303)


@router.get("/account/withdraw", response_class=HTMLResponse)
async def withdraw_form(request: Request, error: str = ""):
    require_role(request, "seeker", "company", "operator", "manager")
    user = request.session
    return templates.TemplateResponse(
        request=request, name="account/withdraw.html", context={
            "request": request, "page_title": "회원탈퇴",
            "user_name": user.get("name", ""),
            "user_role": user.get("role", "seeker"),
            "error": error,
        }
    )


@router.get("/account/consent", response_class=HTMLResponse)
async def consent_page(request: Request, error: str = "", success: str = ""):
    require_role(request, "seeker", "company", "operator", "manager")
    user = request.session
    conn = get_sqlite()
    try:
        user_row = conn.execute(
            "SELECT agreed_marketing_at FROM users WHERE id=?", (user["id"],)
        ).fetchone()
        profile = None
        access_logs = []
        if user.get("role") == "seeker":
            profile = conn.execute(
                "SELECT consent_sensitive, consented_at, consent_withdrawn_at, disability_visibility FROM seeker_profiles WHERE user_id=?",
                (user["id"],),
            ).fetchone()
            access_logs = conn.execute(
                """SELECT al.created_at, al.purpose,
                          u.name AS viewer_name, u.role AS viewer_role,
                          c.company_name
                   FROM access_log al
                   JOIN users u ON al.viewer_id = u.id
                   LEFT JOIN companies c ON u.id = c.user_id
                   WHERE al.seeker_user_id = ?
                   ORDER BY al.created_at DESC
                   LIMIT 5""",
                (user["id"],),
            ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="account/consent.html", context={
            "request": request, "page_title": "개인정보 관리",
            "user_name": user.get("name", ""),
            "user_role": user.get("role", "seeker"),
            "user_row": user_row,
            "profile": profile,
            "access_logs": access_logs,
            "purpose_labels": PURPOSE_LABELS,
            "error": error, "success": success,
        }
    )


@router.post("/account/consent/sensitive")
async def withdraw_sensitive_consent(
    request: Request,
    current_password: str = Form(...),
):
    from datetime import datetime
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT id, password FROM users WHERE id=?", (user["id"],)
        ).fetchone()
        if not row or not verify_password(current_password, row["password"]):
            return RedirectResponse(url="/account/consent?error=wrong", status_code=303)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """UPDATE seeker_profiles SET
               consent_sensitive=0,
               consented_at=NULL,
               consent_withdrawn_at=?,
               disability_type_id=NULL,
               severity='경증'
               WHERE user_id=?""",
            (now, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/account/consent?success=withdrawn", status_code=303)


@router.post("/account/consent/sensitive/restore")
async def restore_sensitive_consent(request: Request):
    from datetime import datetime
    user = require_role(request, "seeker")
    conn = get_sqlite()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = conn.execute(
            "SELECT id FROM seeker_profiles WHERE user_id=?", (user["id"],)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE seeker_profiles SET consent_sensitive=1, consented_at=?, consent_withdrawn_at=NULL WHERE user_id=?",
                (now, user["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO seeker_profiles (user_id, consent_sensitive, consented_at) VALUES (?,1,?)",
                (user["id"], now),
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/profile?success=1", status_code=303)


@router.post("/account/consent/visibility")
async def update_visibility(
    request: Request,
    disability_visibility: str = Form(...),
):
    user = require_role(request, "seeker")
    if disability_visibility not in ("public", "manager_only", "private"):
        return RedirectResponse(url="/account/consent?error=invalid", status_code=303)
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE seeker_profiles SET disability_visibility=? WHERE user_id=?",
            (disability_visibility, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/account/consent?success=visibility", status_code=303)


@router.get("/account/data-download")
async def data_download(request: Request):
    user = require_role(request, "seeker")
    uid = user["id"]
    conn = get_sqlite()
    try:
        u = conn.execute(
            "SELECT name, phone, email, created_at FROM users WHERE id=?", (uid,)
        ).fetchone()
        profile = conn.execute(
            "SELECT * FROM seeker_profiles WHERE user_id=?", (uid,)
        ).fetchone()
        certs = conn.execute(
            "SELECT cert_name, cert_date, issuing_org FROM seeker_certifications WHERE user_id=?", (uid,)
        ).fetchall()
        apps = conn.execute(
            """SELECT c.status, c.created_at, jp.title AS job_title
               FROM candidacies c
               JOIN job_postings jp ON c.job_id = jp.id
               WHERE c.seeker_user_id=?
               ORDER BY c.created_at DESC""",
            (uid,),
        ).fetchall()
        resumes = conn.execute(
            "SELECT name, desired_job, work_pref, created_at FROM resumes WHERE user_id=?", (uid,)
        ).fetchall()
    finally:
        conn.close()

    payload = {
        "user": dict(u) if u else {},
        "profile": dict(profile) if profile else {},
        "certifications": [dict(r) for r in certs],
        "applications": [dict(r) for r in apps],
        "resumes": [dict(r) for r in resumes],
    }
    name = (user.get("name") or "data").replace(" ", "_")
    resp = JSONResponse(content=payload)
    resp.headers["Content-Disposition"] = f'attachment; filename="{name}_data.json"'
    return resp


@router.post("/account/consent/marketing")
async def toggle_marketing_consent(request: Request):
    from datetime import datetime
    user = require_role(request, "seeker", "company", "operator", "manager")
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT agreed_marketing_at FROM users WHERE id=?", (user["id"],)
        ).fetchone()
        if row and row["agreed_marketing_at"]:
            conn.execute("UPDATE users SET agreed_marketing_at=NULL WHERE id=?", (user["id"],))
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("UPDATE users SET agreed_marketing_at=? WHERE id=?", (now, user["id"]))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/account/consent?success=marketing", status_code=303)


@router.post("/account/withdraw")
async def withdraw_submit(
    request: Request,
    current_password: str = Form(...),
    reason: str = Form(""),
):
    from datetime import datetime
    user = require_role(request, "seeker", "company", "operator", "manager")
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT id, password FROM users WHERE id=?", (user["id"],)
        ).fetchone()
        if not row or not verify_password(current_password, row["password"]):
            return RedirectResponse(url="/account/consent?error=wrong_withdraw", status_code=303)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE users SET is_deleted=1, deleted_at=?, name='탈퇴회원', phone='' WHERE id=?",
            (now, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    request.session.clear()
    return RedirectResponse(url="/login?withdrawn=1", status_code=303)
