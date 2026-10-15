import threading
import time

# IP별 시도 타임스탬프 목록
_store = {}
_lock = threading.Lock()

MAX_ATTEMPTS = 5
WINDOW = 300  # 5분

# 같은 서버의 nginx가 넘긴 요청만 XFF 신뢰. 클라이언트 위조값은 앞쪽에 붙으므로 nginx가 추가한 마지막 값 사용
LOCAL_PROXY = ("127.0.0.1", "::1")


def get_client_ip(request):
    if request.client.host in LOCAL_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host


def check_login_rate(ip, limit=MAX_ATTEMPTS):
    now = time.time()
    cutoff = now - WINDOW
    with _lock:
        timestamps = [t for t in _store.get(ip, []) if t > cutoff]
        _store[ip] = timestamps
        return len(timestamps) >= limit


def record_login_attempt(ip):
    now = time.time()
    cutoff = now - WINDOW
    with _lock:
        timestamps = [t for t in _store.get(ip, []) if t > cutoff]
        timestamps.append(now)
        _store[ip] = timestamps


def clear_login_attempts(ip):
    with _lock:
        _store.pop(ip, None)
