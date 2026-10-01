import json

from core.db import get_sqlite
from tests.conftest import login


def saved(username):
    conn = get_sqlite()
    row = conn.execute("SELECT accessibility_settings FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return json.loads(row["accessibility_settings"])


def test_page_renders(client):
    login(client, "seeker1")
    r = client.get("/account/accessibility")
    assert r.status_code == 200
    assert "접근성 설정" in r.text
    assert "쉬운 화면" in r.text
    assert "입력 지연시간" in r.text


def test_page_requires_login(client):
    r = client.get("/account/accessibility", follow_redirects=False)
    assert r.status_code == 303


def test_form_saves_new_settings(client):
    login(client, "seeker1")
    r = client.post(
        "/account/accessibility",
        data={"easy_mode": "on", "input_delay": "500", "dwell_ms": "2000", "font_size": "100", "tts_voice": "F1", "tts_speed": "normal"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    s = saved("seeker1")
    assert s["easy_mode"] is True
    assert s["input_delay"] == 500
    assert s["dwell_ms"] == 2000


def test_form_invalid_values_fall_back(client):
    login(client, "seeker1")
    client.post(
        "/account/accessibility",
        data={"input_delay": "9999", "dwell_ms": "1234", "font_size": "100", "tts_voice": "F1", "tts_speed": "normal"},
        follow_redirects=False,
    )
    s = saved("seeker1")
    assert s["input_delay"] == 0
    assert s["dwell_ms"] == 1500


def test_form_keeps_dwell_read(client):
    login(client, "seeker1")
    client.post("/api/accessibility", json={"dwell_read": True})
    client.post(
        "/account/accessibility",
        data={"font_size": "100", "tts_voice": "F1", "tts_speed": "normal"},
        follow_redirects=False,
    )
    s = saved("seeker1")
    assert s["dwell_read"] is True


def test_api_keeps_new_keys(client):
    login(client, "seeker1")
    r = client.post("/api/accessibility", json={"easy_mode": True, "input_delay": 1000, "dwell_ms": 3000})
    assert r.json()["ok"]
    s = saved("seeker1")
    assert s["easy_mode"] is True
    assert s["input_delay"] == 1000
    assert s["dwell_ms"] == 3000


def test_easy_mode_class_on_body(client):
    login(client, "seeker1")
    client.post("/api/accessibility", json={"easy_mode": True})
    html = client.get("/").text
    assert "easy-mode" in html
