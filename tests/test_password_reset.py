import re

import pytest

from core.db import get_sqlite
from core.rate_limit import _store
from tests.conftest import login


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr("routers.auth.send_mail", lambda to, subject, body: sent.append((to, body)) or True)
    _store.clear()
    return sent


def _request(client, username="seeker1", email="seeker1@example.com"):
    return client.post("/forgot-password", data={"username": username, "email": email}, follow_redirects=False)


def _token(outbox):
    return re.search(r"token=([\w-]+)", outbox[-1][1]).group(1)


def test_reset_link_sent(client, outbox):
    r = _request(client, email="SEEKER1@example.com")
    assert r.headers["location"] == "/forgot-password?sent=1"
    assert outbox[0][0] == "SEEKER1@example.com"
    assert "/reset-password?token=" in outbox[0][1]


def test_unknown_account_same_response(client, outbox):
    r = _request(client, email="nobody@example.com")
    assert r.headers["location"] == "/forgot-password?sent=1"
    assert outbox == []


def test_manager_redirected(client, outbox):
    r = _request(client, "counsel1", "counsel1@example.com")
    assert "error=manager" in r.headers["location"]
    assert outbox == []


def test_reset_password_flow(client, outbox):
    _request(client)
    token = _token(outbox)
    assert "새 비밀번호" in client.get(f"/reset-password?token={token}").text

    r = client.post("/reset-password", data={
        "token": token, "new_password": "newpass12345", "confirm_password": "newpass12345",
    }, follow_redirects=False)
    assert r.headers["location"] == "/login?reset=1"
    assert login(client, "seeker1", "newpass12345").headers["location"] == "/"

    r = client.post("/reset-password", data={
        "token": token, "new_password": "other1234567", "confirm_password": "other1234567",
    }, follow_redirects=False)
    assert "error" not in r.headers["location"]
    assert "만료" in client.get(f"/reset-password?token={token}").text


def test_reset_mismatch_and_short(client, outbox):
    _request(client)
    token = _token(outbox)
    r = client.post("/reset-password", data={
        "token": token, "new_password": "newpass12345", "confirm_password": "newpass99999",
    }, follow_redirects=False)
    assert "error=mismatch" in r.headers["location"]
    r = client.post("/reset-password", data={
        "token": token, "new_password": "short", "confirm_password": "short",
    }, follow_redirects=False)
    assert "error=short" in r.headers["location"]


def test_new_request_invalidates_old_token(client, outbox):
    _request(client)
    old = _token(outbox)
    _request(client)
    assert "만료" in client.get(f"/reset-password?token={old}").text
    assert "새 비밀번호" in client.get(f"/reset-password?token={_token(outbox)}").text


def test_expired_token(client, outbox):
    _request(client)
    token = _token(outbox)
    conn = get_sqlite()
    conn.execute("UPDATE password_resets SET expires_at=datetime('now','localtime','-1 minutes')")
    conn.commit()
    conn.close()
    assert "만료" in client.get(f"/reset-password?token={token}").text


def test_reset_rate_limit(client, outbox):
    for _ in range(5):
        _request(client, email="nobody@example.com")
    assert "error=rate_limit" in _request(client).headers["location"]


def test_signup_requires_email(client):
    r = client.post("/signup", data={
        "username": "no_mail", "password": "testpass1234", "confirm_password": "testpass1234",
        "name": "메일없음", "role": "seeker", "agree_terms": "1", "agree_privacy": "1",
    }, follow_redirects=False)
    assert "error=email_required" in r.headers["location"]


def test_signup_password_policy(client):
    base = {
        "username": "pw_user", "name": "정책", "email": "pw@example.com", "role": "seeker",
        "agree_terms": "1", "agree_privacy": "1",
    }
    r = client.post("/signup", data={**base, "password": "short123", "confirm_password": "short123"}, follow_redirects=False)
    assert "error=short" in r.headers["location"]
    r = client.post("/signup", data={**base, "password": "testpass1234", "confirm_password": "testpass9999"}, follow_redirects=False)
    assert "error=mismatch" in r.headers["location"]
