import time
from types import SimpleNamespace

from core import deps
from core.rate_limit import get_client_ip
from tests.conftest import login


def _req(host, xff=None):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers)


def test_xff_nginx():
    assert get_client_ip(_req("127.0.0.1", "1.1.1.1, 203.0.113.5")) == "203.0.113.5"


def test_xff_spoof():
    assert get_client_ip(_req("198.51.100.7", "1.1.1.1")) == "198.51.100.7"


def test_security_headers(client):
    r = client.get("/login")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_idle_timeout(client, monkeypatch):
    login(client, "seeker1")
    assert client.get("/", follow_redirects=False).status_code == 200
    now = time.time()
    monkeypatch.setattr(deps.time, "time", lambda: now + deps.IDLE_TIMEOUT + 1)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login?error=timeout"
    assert client.get("/applications", follow_redirects=False).status_code == 303


def test_poll_keeps_idle(client, monkeypatch):
    login(client, "seeker1")
    client.get("/")
    now = time.time()
    monkeypatch.setattr(deps.time, "time", lambda: now + deps.IDLE_TIMEOUT - 10)
    client.get("/api/notifications/count")
    monkeypatch.setattr(deps.time, "time", lambda: now + deps.IDLE_TIMEOUT + 1)
    assert client.get("/", follow_redirects=False).status_code == 303

