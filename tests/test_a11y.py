import json
from tests.conftest import login


def test_get_a11y_settings_unauthed(client):
    r = client.get("/api/accessibility")
    assert r.status_code == 200
    data = r.json()
    assert data == {}


def test_get_a11y_settings_default(client):
    login(client, "seeker1")
    r = client.get("/api/accessibility")
    assert r.status_code == 200
    assert r.json() == {}


def test_save_and_load_a11y_settings(client):
    login(client, "seeker1")
    settings = {"font_size": 120, "line_height": 1.8, "contrast": True}
    r = client.post("/api/accessibility", json=settings)
    assert r.status_code == 200
    assert r.json()["ok"]

    r = client.get("/api/accessibility")
    data = r.json()
    assert data["font_size"] == 120
    assert data["contrast"] is True


def test_save_a11y_unauthed(client):
    r = client.post("/api/accessibility", json={"font_size": 120})
    assert r.status_code == 401
