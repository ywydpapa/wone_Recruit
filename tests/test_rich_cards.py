import json
from core.db import get_sqlite
from tests.conftest import login


def test_job_card_shows_salary_icon(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    assert "fa-won-sign" in r.text


def test_job_card_shows_deadline_icon(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    assert "fa-clock" in r.text


def test_job_card_shows_remote_badge(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    # 시드에 재택근무 공고 존재
    assert "재택 가능" in r.text
    assert "badge-green" in r.text


def test_job_card_shows_accommodation_filter(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    assert "편의제공" in r.text


def test_job_card_clickable(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    assert "상세보기" in r.text
