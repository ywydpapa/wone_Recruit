import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from core.constants import PURPOSE_LABELS
from core.db import get_sqlite
from core.deps import check_login, require_role, templates
from core.mail import send_mail
from core.rate_limit import check_login_rate, record_login_attempt, clear_login_attempts, get_client_ip
from core.security import check_password, hash_password, verify_password

router = APIRouter()

RESET_TTL_MIN = 30


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
        if row["must_change_password"]:
            request.session["must_change_password"] = True
            return RedirectResponse(url="/change-password", status_code=303)
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request, error: str = "", sent: str = ""):
    if check_login(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request, name="login/forgot_password.html", context={
            "request": request, "page_title": "비밀번호 찾기",
            "error": error, "sent": sent,
        }
    )


@router.post("/forgot-password")
async def forgot_password_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
):
    key = "reset:" + get_client_ip(request)
    if check_login_rate(key):
        return RedirectResponse(url="/forgot-password?error=rate_limit", status_code=303)
    record_login_attempt(key)

    email = email.strip()
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT id, role FROM users WHERE username=? AND LOWER(email)=LOWER(?) AND email<>'' AND is_deleted=0",
            (username.strip(), email),
        ).fetchone()
        if row and row["role"] == "manager":
            return RedirectResponse(url="/forgot-password?error=manager", status_code=303)
        token = None
        if row:
            token = secrets.token_urlsafe(32)
            conn.execute(
                "UPDATE password_resets SET used_at=datetime('now','localtime') WHERE user_id=? AND used_at IS NULL",
                (row["id"],),
            )
            conn.execute(
                "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?,?,datetime('now','localtime',?))",
                (row["id"], _hash_token(token), f"+{RESET_TTL_MIN} minutes"),
            )
            conn.commit()
    finally:
        conn.close()

    # 계정 존재 여부가 드러나지 않도록 결과와 관계없이 동일하게 안내함
    if token:
        base = os.getenv("BASE_URL") or str(request.base_url)
        link = f"{base.rstrip('/')}/reset-password?token={token}"
        await asyncio.to_thread(
            send_mail, email, "[WONE Recruit] 비밀번호 재설정 안내",
            f"아래 링크에서 새 비밀번호를 설정해 주세요. 링크는 {RESET_TTL_MIN}분 동안 한 번만 사용할 수 있습니다.\n\n"
            f"{link}\n\n"
            "본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다.",
        )
    return RedirectResponse(url="/forgot-password?sent=1", status_code=303)


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _find_reset(conn, token):
    return conn.execute(
        "SELECT id, user_id FROM password_resets "
        "WHERE token_hash=? AND used_at IS NULL AND expires_at > datetime('now','localtime')",
        (_hash_token(token),),
    ).fetchone()


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = "", error: str = ""):
    conn = get_sqlite()
    try:
        valid = bool(token) and _find_reset(conn, token) is not None
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="login/reset_password.html", context={
            "request": request, "page_title": "비밀번호 재설정",
            "token": token, "valid": valid, "error": error,
        }
    )


@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    back = f"/reset-password?token={quote(token)}"
    if new_password != confirm_password:
        return RedirectResponse(url=back + "&error=mismatch", status_code=303)
    pw_err = check_password(new_password)
    if pw_err:
        return RedirectResponse(url=f"{back}&error={pw_err}", status_code=303)
    conn = get_sqlite()
    try:
        rst = _find_reset(conn, token)
        if not rst:
            return RedirectResponse(url=back, status_code=303)
        conn.execute(
            "UPDATE users SET password=?, must_change_password=0 WHERE id=?",
            (hash_password(new_password), rst["user_id"]),
        )
        conn.execute(
            "UPDATE password_resets SET used_at=datetime('now','localtime') WHERE user_id=? AND used_at IS NULL",
            (rst["user_id"],),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/login?reset=1", status_code=303)


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, error: str = ""):
    if not check_login(request) or not request.session.get("must_change_password"):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="login/change_password.html", context={
            "request": request, "page_title": "비밀번호 변경",
            "error": error,
        }
    )


@router.post("/change-password")
async def change_password_submit(
    request: Request,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    if not check_login(request) or not request.session.get("must_change_password"):
        return RedirectResponse(url="/login", status_code=303)
    if new_password != confirm_password:
        return RedirectResponse(url="/change-password?error=mismatch", status_code=303)
    pw_err = check_password(new_password)
    if pw_err:
        return RedirectResponse(url=f"/change-password?error={pw_err}", status_code=303)
    uid = request.session["id"]
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE users SET password=?, must_change_password=0 WHERE id=?",
            (hash_password(new_password), uid),
        )
        conn.commit()
    finally:
        conn.close()
    request.session.pop("must_change_password", None)
    return RedirectResponse(url="/", status_code=303)


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
    confirm_password: str = Form(...),
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
    email = email.strip()
    if "@" not in email:
        return RedirectResponse(url="/signup?error=email_required", status_code=303)
    if password != confirm_password:
        return RedirectResponse(url="/signup?error=mismatch", status_code=303)
    pw_err = check_password(password)
    if pw_err:
        return RedirectResponse(url=f"/signup?error={pw_err}", status_code=303)
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
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT username, name, email, phone FROM users WHERE id=?", (user["id"],)
        ).fetchone()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="account/mypage.html", context={
            "request": request, "page_title": "마이페이지",
            "user_name": user.get("name", ""),
            "user_role": user.get("role", "seeker"),
            "account": row,
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
    pw_err = check_password(new_password)
    if pw_err:
        return RedirectResponse(url=f"/account/password?error={pw_err}", status_code=303)
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
async def withdraw_consent(
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
async def restore_consent(request: Request):
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
    # 한글 파일명은 헤더에 그대로 넣을 수 없어 RFC 5987 형식을 사용함
    resp.headers["Content-Disposition"] = f"attachment; filename=\"data.json\"; filename*=UTF-8''{quote(name + '_data.json')}"
    return resp


@router.post("/account/consent/marketing")
async def toggle_marketing(request: Request):
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
