import json

from core.db import get_sqlite
from tests.conftest import login


def saved(username):
    conn = get_sqlite()
    row = conn.execute("SELECT accessibility_settings FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return json.loads(row["accessibility_settings"])


def test_save_a11y_whitelist(client):
    login(client, "seeker1")
    r = client.post("/api/accessibility", json={"font_size": 150, "high_contrast": True, "tts_voice": "X1", "theme": "dark"})
    assert r.json()["ok"]
    s = saved("seeker1")
    assert s["font_size"] == 150
    assert s["high_contrast"] is True
    assert s["tts_voice"] == "F1"
    assert "theme" not in s


def test_a11y_applied_to_page(client):
    login(client, "seeker1")
    client.post("/api/accessibility", json={"font_size": 200, "high_contrast": True})
    html = client.get("/").text
    assert 'class="font-xl"' in html
    assert "theme-high-contrast" in html
    assert 'id="a11yWidget"' in html


def test_save_a11y_unauthed(client):
    r = client.post("/api/accessibility", json={"font_size": 150}, follow_redirects=False)
    assert r.status_code == 303


def test_tts_validation(client):
    login(client, "seeker1")
    r = client.post("/api/tts", data={"text": "안녕", "voice": "X1", "speed": "normal"})
    assert r.status_code == 400
