import json
import logging
import os
import re
import time

import httpx
from fastapi import APIRouter, Request

from core.deps import require_role

router = APIRouter()
log = logging.getLogger(__name__)

# 미설정 시 모델 미사용. 폐쇄망 서버의 Ollama 모델명 지정
NLU_MODEL = os.getenv("NLU_MODEL", "")
NLU_URL = os.getenv("NLU_URL", "http://localhost:11434")
NLU_TIMEOUT = float(os.getenv("NLU_TIMEOUT", "3"))
# 발화 원문은 개인정보 포함 가능성으로 기본 미기록. 학습 데이터 수집 시에만 사용
NLU_LOG = os.getenv("NLU_LOG") == "1"

# 학습 데이터(nlu-test/gen_data.py)와 동일 문구 유지 필요
SYS = "화면 음성 명령을 action, target, field, ord, value JSON으로 변환함. 이름은 화면 목록에서만 고름."
# 구직자 목표 의도. target은 화면 목록이 아닌 고정 목록으로 검사함
FIXED_TARGETS = {
    "job_search": {"맞춤", ""},
    "open_item": {""},
    "read_item": {""},
    "bookmark": {""},
    "resume_new": {""},
    "resume_copy": {""},
    "resume_act": {"수정", "삭제", "복사", "보기", "대표"},
    "status_read": {""},
    "withdraw": {""},
    "proposal_respond": {"수락", "거절"},
    "schedule_read": {""},
    "inbox_read": {"메시지", "알림"},
    "a11y_set": {"글자크게", "글자보통", "고대비", "고대비끄기", "쉬운화면", "쉬운화면끄기", "다크모드", "라이트모드"},
}
ACTIONS = ["fill", "focus", "add_row", "fill_row", "delete_row", "edit_row", "open_section", "ask_fields", "dictate",
           "click", "nav", "none", "consult_request", "send_message", "import_section", *FIXED_TARGETS]
SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ACTIONS},
        "target": {"type": "string"}, "field": {"type": "string"},
        "ord": {"type": "integer"}, "value": {"type": "string"},
    },
    "required": ["action", "target", "field", "ord", "value"],
}
NONE = {"action": "none"}
# dictate 대상은 자기소개서 항목명이라 화면 목록 검사 제외
FREE_TARGET = {"dictate", "none", "consult_request", "send_message"}
MAX_NAMES = 60


def squash(s):
    return re.sub(r"\s", "", s or "")


# 학습 시 등급 숫자 변환을 모델에 맡기지 않았으므로 비교 전 양쪽 동일하게 변환
def grade(s):
    return re.sub(r"([일이삼])\s*급", lambda m: "123"["일이삼".index(m[1])] + "급", s)


def names(body, key):
    v = body.get(key)
    if not isinstance(v, list):
        return []
    return [str(x).strip()[:30] for x in v if str(x).strip()][:MAX_NAMES]


# 모델 오답은 실행하지 않고 미인식으로 처리. 틀린 동작보다 재질문이 안전함
def check(out, text, screen):
    act = out.get("action")
    if act not in ACTIONS or act == "none":
        return NONE
    target = (out.get("target") or "").strip()
    field = (out.get("field") or "").strip()
    value = grade((out.get("value") or "").strip())
    ord_ = out.get("ord") if isinstance(out.get("ord"), int) else 0
    # 구직자 목표 의도는 화면 목록 대신 고정 목록으로 검사하고 field는 항상 빈 값만 허용함
    if act in FIXED_TARGETS:
        if target not in FIXED_TARGETS[act] or field:
            return NONE
    else:
        # 띄어쓰기 차이는 동일 이름으로 처리
        known = {squash(n) for n in sum(screen.values(), [])}
        if target and act not in FREE_TARGET and squash(target) not in known:
            return NONE
        if field and squash(field) not in known:
            return NONE
    if value and squash(value) not in squash(grade(text)):
        return NONE
    # 칸 이름을 말했는데 모델이 칸을 빠뜨린 경우 대표 칸 오입력 방지
    if act == "edit_row" and not field and any(f in text for f in screen["칸"]):
        return NONE
    return {"action": act, "target": target, "field": field, "ord": ord_, "value": value}


@router.post("/api/nlu")
async def nlu(request: Request):
    require_role(request, "seeker", "company", "manager", "operator")
    if not NLU_MODEL:
        return NONE
    try:
        body = await request.json()
    except ValueError:
        return NONE
    text = str(body.get("text") or "").strip()[:200]
    if not text:
        return NONE
    screen = {k: names(body, key) for k, key in [("섹션", "sections"), ("칸", "fields"), ("버튼", "buttons"), ("메뉴", "menus")]}
    scr = "\n".join(f"{k}: {', '.join(v)}" for k, v in screen.items())
    req = {
        "model": NLU_MODEL, "stream": False, "format": SCHEMA,
        "options": {"temperature": 0, "num_predict": 80},
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": f"{scr}\n발화: {text}"}],
    }
    t = time.time()
    try:
        async with httpx.AsyncClient(timeout=NLU_TIMEOUT) as client:
            r = await client.post(NLU_URL + "/api/chat", json=req)
        r.raise_for_status()
        out = json.loads(r.json()["message"]["content"])
    except httpx.TimeoutException:
        log.info("nlu 시간 초과 %.1fs", time.time() - t)
        return NONE
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        log.warning("nlu 호출 실패")
        return NONE
    res = check(out if isinstance(out, dict) else {}, text, screen)
    log.info("nlu %s %.1fs", res["action"], time.time() - t)
    if NLU_LOG:
        log.info("nlu 발화 %s -> %s / 결과 %s", text, out, res)
    return res
