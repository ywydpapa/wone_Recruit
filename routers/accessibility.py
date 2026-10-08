import io
import json
import logging
import os

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from core.db import get_sqlite
from core.tts_text import ko_text
from core.deps import require_role, templates

router = APIRouter()
log = logging.getLogger(__name__)

MAX_AUDIO = 2 * 1024 * 1024
# CPU 기준 짧은 발화도 약 7초가 소요되나, small 모델은 짧은 명령 인식률이 낮음. 운영 서버에서 느릴 경우 STT_MODEL로 변경 필요
STT_MODEL = os.getenv("STT_MODEL", "large-v3-turbo")
TTS_DIR = os.getenv("TTS_DIR", "models/supertonic")
TTS_VOICES = {"F1", "M1"}
TTS_SPEEDS = {"slow": 0.8, "normal": 0.9, "fast": 1.05}
FONT_SIZES = {100, 150, 200}
INPUT_DELAYS = {0, 500, 1000}
DWELL_OPTS = {1000, 1500, 2000, 3000}
_whisper = None
_tts = None
_tts_styles = {}
ROLES = ("seeker", "company", "manager", "operator")
STT_PROMPT = (
    "하이원, 이력서 작성. 이력서 항목을 받아적습니다. 학력, 경력, 자격증, 어학, 회사명, 부서, 직책, 직급, 입사, 퇴사, 취득일, 재직중, 삭제, "
    "사원, 주임, 대리, 과장, 차장, 부장, 선임, 책임, 수석, 팀장, 파트장, TL, PM, "
    "MLCC, PCB, Mask, Etching, NAND, eSSD, 불량분석, 분석기술, 양산기술, 구매전략, 외자구매, 프라이싱, "
    "정규직, 계약직, 정보처리기사, 컴퓨터활용능력, 워드프로세서, 사회복지사, 2019년 3월 같은 날짜 표현."
)


# whisper/supertonic을 모듈 로드 시 임포트하면 프로세스 종료 때 abort(134)가 발생하므로 최초 사용 시점에 로드함
def get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(STT_MODEL, device="cpu", compute_type="int8")
    return _whisper


def transcribe(model, data):
    segs, _ = model.transcribe(
        io.BytesIO(data),
        language="ko",
        beam_size=1,
        vad_filter=True,
        initial_prompt=STT_PROMPT,
    )
    return "".join(s.text for s in segs).strip()


# 녹음은 메모리에서만 처리하며, 인식 결과는 로그에 남기지 않음
@router.post("/api/stt")
async def stt(request: Request, audio: UploadFile = File(...)):
    require_role(request, *ROLES)
    data = await audio.read(MAX_AUDIO + 1)
    if len(data) > MAX_AUDIO:
        return JSONResponse({"error": "음성이 너무 길어요"}, status_code=413)
    try:
        model = await run_in_threadpool(get_whisper)
    except Exception:
        log.exception("whisper 모델 로드 실패")
        return JSONResponse({"error": "지금은 음성 인식을 쓸 수 없어요"}, status_code=503)
    try:
        text = await run_in_threadpool(transcribe, model, data)
    except Exception:
        log.warning("음성 디코딩 실패")
        return JSONResponse({"error": "음성을 처리하지 못했어요"}, status_code=400)
    return {"text": text}


def get_tts():
    global _tts
    if _tts is None:
        from supertonic import TTS
        _tts = TTS(model="supertonic-3", model_dir=TTS_DIR, auto_download=False)
    return _tts


def get_voice_style(model, voice):
    if voice not in _tts_styles:
        _tts_styles[voice] = model.get_voice_style(voice)
    return _tts_styles[voice]


def synth_wav(model, text, voice, speed):
    style = get_voice_style(model, voice)
    import soundfile as sf
    wav, _ = model.synthesize(ko_text(text), voice_style=style, lang="ko", total_steps=4, speed=speed)
    buf = io.BytesIO()
    sf.write(buf, wav.squeeze(), model.sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


# 텍스트는 로그에 남기지 않음
@router.post("/api/tts")
async def tts(
    request: Request,
    text: str = Form(""),
    voice: str = Form(...),
    speed: str = Form(...),
):
    require_role(request, *ROLES)
    text = text.strip()
    if not text or len(text) > 300:
        return JSONResponse({"error": "내용이 없거나 너무 깁니다"}, status_code=400)
    if voice not in TTS_VOICES:
        return JSONResponse({"error": "지원하지 않는 음성입니다"}, status_code=400)
    if speed not in TTS_SPEEDS:
        return JSONResponse({"error": "지원하지 않는 속도입니다"}, status_code=400)
    try:
        model = await run_in_threadpool(get_tts)
    except Exception:
        log.exception("supertonic 모델 로드 실패")
        return JSONResponse({"error": "음성 합성 모델을 사용할 수 없습니다"}, status_code=503)
    try:
        wav = await run_in_threadpool(synth_wav, model, text, voice, TTS_SPEEDS[speed])
    except Exception as e:
        log.warning("tts 합성 실패: %s", type(e).__name__)
        return JSONResponse({"error": "읽을 수 없는 글자가 있습니다"}, status_code=400)
    return Response(wav, media_type="audio/wav")


def to_int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# 새 설정 키는 여기 추가해야 저장됨
def normalize_a11y(body):
    tts_voice = body.get("tts_voice", "F1")
    tts_speed = body.get("tts_speed", "normal")
    font_size = to_int(body.get("font_size", 100), 100)
    input_delay = to_int(body.get("input_delay", 0), 0)
    dwell_ms = to_int(body.get("dwell_ms", 1500), 1500)
    return {
        "high_contrast": bool(body.get("high_contrast", False)),
        "font_size": font_size if font_size in FONT_SIZES else 100,
        "large_target": bool(body.get("large_target", False)),
        "easy_mode": bool(body.get("easy_mode", False)),
        "head_mouse": bool(body.get("head_mouse", False)),
        "dwell_read": bool(body.get("dwell_read", False)),
        "click_read": bool(body.get("click_read", False)),
        "input_delay": input_delay if input_delay in INPUT_DELAYS else 0,
        "dwell_ms": dwell_ms if dwell_ms in DWELL_OPTS else 1500,
        "tts_voice": tts_voice if tts_voice in TTS_VOICES else "F1",
        "tts_speed": tts_speed if tts_speed in TTS_SPEEDS else "normal",
        "voice_auto": bool(body.get("voice_auto", False)),
        "sr_mode": bool(body.get("sr_mode", False)),
    }


@router.post("/api/accessibility")
async def save_accessibility(request: Request):
    user = require_role(request, *ROLES)
    body = await request.json()
    settings = json.dumps(normalize_a11y(body))
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE users SET accessibility_settings=? WHERE id=?",
            (settings, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.get("/account/accessibility", response_class=HTMLResponse)
async def accessibility_form(request: Request, success: str = ""):
    user = require_role(request, *ROLES)
    return templates.TemplateResponse(
        request=request, name="account/accessibility.html", context={
            "request": request, "page_title": "접근성 설정",
            "user_name": user["name"], "user_role": user["role"],
            "a11y": request.state.a11y, "success": success,
        }
    )


@router.post("/account/accessibility")
async def accessibility_submit(
    request: Request,
    high_contrast: str = Form(None),
    font_size: str = Form("100"),
    large_target: str = Form(None),
    easy_mode: str = Form(None),
    head_mouse: str = Form(None),
    dwell_ms: str = Form("1500"),
    input_delay: str = Form("0"),
    click_read: str = Form(None),
    tts_voice: str = Form("F1"),
    tts_speed: str = Form("normal"),
    voice_auto: str = Form(None),
    sr_mode: str = Form(None),
):
    user = require_role(request, *ROLES)
    # 페이지에 없는 항목(dwell_read 등)은 기존값을 유지함
    body = dict(request.state.a11y)
    body.update({
        "high_contrast": bool(high_contrast),
        "font_size": font_size,
        "large_target": bool(large_target),
        "easy_mode": bool(easy_mode),
        "head_mouse": bool(head_mouse),
        "dwell_ms": dwell_ms,
        "input_delay": input_delay,
        "click_read": bool(click_read),
        "tts_voice": tts_voice,
        "tts_speed": tts_speed,
        "voice_auto": bool(voice_auto),
        "sr_mode": bool(sr_mode),
    })
    settings = json.dumps(normalize_a11y(body))
    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE users SET accessibility_settings=? WHERE id=?",
            (settings, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/account/accessibility?success=1", status_code=303)
