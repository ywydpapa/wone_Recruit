import json
from urllib.parse import urlencode

from core.db import get_sqlite
from tests.conftest import login


def test_job_list_company(client):
    login(client, "comp1")
    r = client.get("/company/jobs")
    assert r.status_code == 200


def test_job_create(client):
    login(client, "comp1")
    r = client.post("/company/jobs/new", data={
        "title": "테스트 공고",
        "region_id": 1,
        "employment_type": "정규직",
        "remote_available": "1",
        "salary": "월 200만원",
        "deadline": "2026-12-31",
        "description": "테스트입니다",
        "status": "open",
    }, follow_redirects=False)
    assert r.status_code == 303


def test_job_create_with_accommodations(client):
    login(client, "comp1")
    fields = [
        ("title", "편의시설 테스트 공고"),
        ("region_id", "1"),
        ("employment_type", "정규직"),
        ("remote_available", "1"),
        ("work_start_time", "10:00"),
        ("work_end_time", "16:00"),
        ("work_days", "월~목"),
        ("flexible_hours", "1"),
        ("accommodations_provided", "휠체어접근"),
        ("accommodations_provided", "재택근무"),
        ("accommodations_note", "높이조절 책상 제공"),
        ("preferred_disability", "지체"),
        ("preferred_disability", "뇌병변"),
        ("preferred_severity", "경증"),
        ("min_work_hours", "6"),
        ("benefits", "4대보험, 식대"),
        ("requirements", "컴활 2급"),
        ("salary", "월 250만원"),
        ("deadline", "2026-12-31"),
        ("description", "편의시설 테스트"),
        ("status", "open"),
    ]
    r = client.post(
        "/company/jobs/new",
        content=urlencode(fields, doseq=True),
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    conn = get_sqlite()
    try:
        job = conn.execute(
            "SELECT * FROM job_postings WHERE title='편의시설 테스트 공고'"
        ).fetchone()
    finally:
        conn.close()
    assert job is not None
    assert job["work_start_time"] == "10:00"
    assert job["work_end_time"] == "16:00"
    assert job["work_days"] == "월~목"
    assert job["flexible_hours"] == 1
    accom = json.loads(job["accommodations_provided"])
    assert "휠체어접근" in accom
    assert "재택근무" in accom
    assert job["accommodations_note"] == "높이조절 책상 제공"
    pref = json.loads(job["preferred_disability"])
    assert "지체" in pref
    assert "뇌병변" in pref
    assert job["preferred_severity"] == "경증"
    assert job["min_work_hours"] == 6
    assert job["benefits"] == "4대보험, 식대"
    assert job["requirements"] == "컴활 2급"


def test_job_search_seeker(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    assert "사무지원" in r.text


def test_job_search_with_filter(client):
    login(client, "seeker1")
    r = client.get("/jobs?sido=부산광역시")
    assert r.status_code == 200


def test_job_search_by_work_hours(client):
    login(client, "seeker1")
    r = client.get("/jobs?max_hours=4")
    assert r.status_code == 200
    assert "4h" in r.text or "파일링" in r.text or "파트타임" in r.text or "리뷰" in r.text


def test_job_detail(client):
    login(client, "seeker1")
    r = client.get("/jobs/1")
    assert r.status_code == 200
    assert "지원하기" in r.text


def test_job_detail_shows_accommodations(client):
    login(client, "seeker1")
    r = client.get("/jobs/1")
    assert r.status_code == 200
    assert "근무 시간" in r.text
    assert "편의 제공" in r.text or "추가 편의사항" in r.text
