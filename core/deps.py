import json

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from core.csrf import csrf_input_html

templates = Jinja2Templates(directory="templates")


def _fromjson(v):
    if not v:
        return []
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return []


templates.env.filters["fromjson"] = _fromjson


def _fdate(v):
    if not v:
        return "-"
    return v[:10]


def _fdatetime(v):
    if not v:
        return "-"
    return v[:16]


def _region(row, fallback="미지정"):
    sido = ""
    sigungu = ""
    if isinstance(row, dict):
        sido = row.get("region_sido") or ""
        sigungu = row.get("region_sigungu") or ""
    else:
        sido = getattr(row, "region_sido", "") or ""
        sigungu = getattr(row, "region_sigungu", "") or ""
    text = f"{sido} {sigungu}".strip()
    return text or fallback


templates.env.filters["fdate"] = _fdate
templates.env.filters["fdatetime"] = _fdatetime
templates.env.filters["region"] = _region


def _split_steps(v):
    if not v:
        return []
    return [s.strip() for s in v.split(",") if s.strip()]


def _fmt_minutes(v):
    if not v:
        return ""
    v = int(v)
    if v < 60:
        return f"{v}분"
    if v % 60 == 0:
        return f"{v // 60}시간"
    return f"{v // 60}시간 {v % 60}분"


templates.env.filters["split_steps"] = _split_steps
templates.env.filters["fmt_minutes"] = _fmt_minutes

_orig_response = templates.TemplateResponse


def _patched_response(*args, **kwargs):
    ctx = kwargs.get("context")
    if ctx is None and len(args) > 1:
        ctx = args[1]
    req = kwargs.get("request") or (ctx.get("request") if ctx else None)
    if req is not None and ctx is not None:
        token = getattr(req.state, "csrf_token", "")
        ctx.setdefault("csrf_input", csrf_input_html(token))
    return _orig_response(*args, **kwargs)


templates.TemplateResponse = _patched_response


def check_login(request):
    return request.session.get("logined", False)


def get_current_user(request):
    return {
        "id": request.session.get("id"),
        "name": request.session.get("name", ""),
        "role": request.session.get("role", "seeker"),
    }


def require_role(request, *roles):
    if not check_login(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    user = get_current_user(request)
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    return user
