import json
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from core.csrf import csrf_input_html
from core.masking import mask_name, mask_phone, mask_email

templates = Jinja2Templates(directory="templates")

GNB_MENU = [("/jobs", "채용정보"), ("/community", "커뮤니티"), ("/notices", "공지사항")]
MYPAGE_MENU = [
    ("신청현황", [("/status", "전체 현황"), ("/applications", "지원 현황"), ("/proposals", "받은 제안"), ("/schedule", "내 일정"), ("/consult", "상담")]),
    ("이력서", [("/profile", "내 프로필"), ("/resumes", "이력서 관리"), ("/profile/views", "열람 현황")]),
    ("관심 공고", [("/bookmarks", "저장 공고"), ("/recent", "최근 본 공고")]),
    ("소통", [("/messages", "메시지"), ("/inquiries", "문의하기")]),
    ("설정", [("/account/mypage", "계정"), ("/account/consent", "개인정보"), ("/account/accessibility", "접근성"), ("/account/notify", "알림 설정"), ("/notifications", "알림")]),
]
MYPAGE_PATHS = tuple(href for _, links in MYPAGE_MENU for href, _ in links) + ("/saved-searches",)
templates.env.globals["gnb_menu"] = GNB_MENU
templates.env.globals["mypage_menu"] = MYPAGE_MENU
# 화면 메뉴에는 없고 음성으로만 이동하는 경로임
INTRO_TITLES = ["지원동기", "성장과정", "성격의 장단점", "입사 후 포부", "직무역량", "자기소개"]
templates.env.globals["voice_links"] = [("음성", [("/", "홈"), ("/resumes/write", "이력서 작성")] + [
    (f"/resumes/write?item={quote(t)}", f"{t} 작성") for t in INTRO_TITLES
])]
templates.env.filters["mypage"] = lambda path: path.startswith(MYPAGE_PATHS)


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
    # sqlite3.Row는 getattr을 지원하지 않음
    keys = row.keys()
    sido = row["region_sido"] if "region_sido" in keys else ""
    sigungu = row["region_sigungu"] if "region_sigungu" in keys else ""
    text = f"{sido or ''} {sigungu or ''}".strip()
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

templates.env.filters["mask_name"] = mask_name
templates.env.filters["mask_phone"] = mask_phone
templates.env.filters["mask_email"] = mask_email

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
