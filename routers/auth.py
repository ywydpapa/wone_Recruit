import sqlite3

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import check_login, require_role, templates
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
        request.session["logined"] = True
        request.session["user_id"] = row["id"]
        request.session["username"] = row["username"]
        request.session["user_name"] = row["name"]
        request.session["user_role"] = row["role"]
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)


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
            "INSERT INTO users (username, password, name, phone, role, agreed_terms_at, agreed_privacy_at, agreed_marketing_at) VALUES (?,?,?,?,?,?,?,?)",
            (username, hash_password(password), name, phone, role, now, now, marketing_at)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return RedirectResponse(url="/signup?error=dup", status_code=303)
    finally:
        conn.close()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/account/mypage", response_class=HTMLResponse)
async def mypage(request: Request):
    user = require_role(request, "seeker", "company", "operator")
    return templates.TemplateResponse(
        request=request, name="account/mypage.html", context={
            "request": request, "page_title": "마이페이지",
            "user_name": user.get("user_name", ""),
            "user_role": user.get("user_role", "seeker"),
        }
    )


@router.get("/account/password", response_class=HTMLResponse)
async def password_change_form(request: Request, error: str = "", success: str = ""):
    require_role(request, "seeker", "company", "operator")
    user = request.session
    return templates.TemplateResponse(
        request=request, name="account/password.html", context={
            "request": request, "page_title": "비밀번호 변경",
            "user_name": user.get("user_name", ""),
            "user_role": user.get("user_role", "seeker"),
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
    user = require_role(request, "seeker", "company", "operator")
    if new_password != confirm_password:
        return RedirectResponse(url="/account/password?error=mismatch", status_code=303)
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return RedirectResponse(url="/account/password?error=short", status_code=303)
    if current_password == new_password:
        return RedirectResponse(url="/account/password?error=same", status_code=303)
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT id, password FROM users WHERE id=?", (user["user_id"],)
        ).fetchone()
        if not row or not verify_password(current_password, row["password"]):
            return RedirectResponse(url="/account/password?error=wrong", status_code=303)
        conn.execute("UPDATE users SET password=? WHERE id=?", (hash_password(new_password), user["user_id"]))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/account/password?success=1", status_code=303)


@router.get("/account/withdraw", response_class=HTMLResponse)
async def withdraw_form(request: Request, error: str = ""):
    require_role(request, "seeker", "company", "operator")
    user = request.session
    return templates.TemplateResponse(
        request=request, name="account/withdraw.html", context={
            "request": request, "page_title": "회원탈퇴",
            "user_name": user.get("user_name", ""),
            "user_role": user.get("user_role", "seeker"),
            "error": error,
        }
    )


@router.get("/account/consent", response_class=HTMLResponse)
async def consent_page(request: Request, error: str = "", success: str = ""):
    require_role(request, "seeker", "company", "operator")
    user = request.session
    conn = get_sqlite()
    try:
        user_row = conn.execute(
            "SELECT agreed_marketing_at FROM users WHERE id=?", (user["user_id"],)
        ).fetchone()
        profile = None
        if user.get("user_role") == "seeker":
            profile = conn.execute(
                "SELECT consent_sensitive, consented_at, consent_withdrawn_at FROM seeker_profiles WHERE user_id=?",
                (user["user_id"],),
            ).fetchone()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="account/consent.html", context={
            "request": request, "page_title": "개인정보 관리",
            "user_name": user.get("user_name", ""),
            "user_role": user.get("user_role", "seeker"),
            "user_row": user_row,
            "profile": profile,
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
            "SELECT id, password FROM users WHERE id=?", (user["user_id"],)
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
            (now, user["user_id"]),
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
            "SELECT id FROM seeker_profiles WHERE user_id=?", (user["user_id"],)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE seeker_profiles SET consent_sensitive=1, consented_at=?, consent_withdrawn_at=NULL WHERE user_id=?",
                (now, user["user_id"]),
            )
        else:
            conn.execute(
                "INSERT INTO seeker_profiles (user_id, consent_sensitive, consented_at) VALUES (?,1,?)",
                (user["user_id"], now),
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/profile?success=1", status_code=303)


@router.post("/account/consent/marketing")
async def toggle_marketing_consent(request: Request):
    from datetime import datetime
    user = require_role(request, "seeker", "company", "operator")
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT agreed_marketing_at FROM users WHERE id=?", (user["user_id"],)
        ).fetchone()
        if row and row["agreed_marketing_at"]:
            conn.execute("UPDATE users SET agreed_marketing_at=NULL WHERE id=?", (user["user_id"],))
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("UPDATE users SET agreed_marketing_at=? WHERE id=?", (now, user["user_id"]))
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
    user = require_role(request, "seeker", "company", "operator")
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT id, password FROM users WHERE id=?", (user["user_id"],)
        ).fetchone()
        if not row or not verify_password(current_password, row["password"]):
            return RedirectResponse(url="/account/withdraw?error=wrong", status_code=303)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE users SET is_deleted=1, deleted_at=?, name='탈퇴회원', phone='' WHERE id=?",
            (now, user["user_id"]),
        )
        conn.commit()
    finally:
        conn.close()
    request.session.clear()
    return RedirectResponse(url="/login?withdrawn=1", status_code=303)
