import json

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def _fromjson(v):
    if not v:
        return []
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return []


templates.env.filters["fromjson"] = _fromjson


def check_login(request: Request) -> bool:
    return request.session.get("logined", False)


def get_current_user(request: Request) -> dict:
    return {
        "user_id": request.session.get("user_id"),
        "user_name": request.session.get("user_name", ""),
        "user_role": request.session.get("user_role", "seeker"),
    }


def require_role(request: Request, *roles: str):
    if not check_login(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    user = get_current_user(request)
    if user["user_role"] not in roles:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    return user
