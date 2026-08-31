import json
from urllib.parse import urlencode

from core.db import get_sqlite
from tests.conftest import login

_FORM_HEADERS = {"content-type": "application/x-www-form-urlencoded"}


def _post_form(client, url, fields, **kwargs):
    return client.post(
        url,
        content=urlencode(fields, doseq=True),
        headers=_FORM_HEADERS,
        **kwargs,
    )


def test_profile_requires_login(client):
    r = client.get("/profile", follow_redirects=False)
    assert r.status_code in (303, 403)


def test_profile_form_renders(client):
    login(client, "seeker1")
    r = client.get("/profile")
    assert r.status_code == 200
    assert "내 프로필" in r.text


def test_profile_save_needs_consent(client):
    login(client, "seeker1")
    r = client.post("/profile", data={
        "disability_type_id": 1, "severity": "경증",
        "consent_sensitive": 0,
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "consent" in r.headers["location"]


def test_profile_save_ok(client):
    login(client, "seeker1")
    r = client.post("/profile", data={
        "disability_type_id": 1, "severity": "중증",
        "gender": "여", "birth_year": 1996, "region_id": 1,
        "desired_job": "사무보조", "work_pref": "재택",
        "education_level": "고졸", "school_name": "", "major": "",
        "career_years": 1, "experience_summary": "테스트",
        "consent_sensitive": 1,
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "success" in r.headers["location"]


def test_profile_v2_save_disability_context(client):
    login(client, "seeker1")
    r = _post_form(client, "/profile", [
        ("disability_type_id", "1"),
        ("severity", "중증"),
        ("gender", "여"),
        ("birth_year", "1996"),
        ("region_id", "1"),
        ("mobility_type", "대중교통"),
        ("commute_max_minutes", "60"),
        ("communication_pref", "문자"),
        ("communication_pref", "수어"),
        ("assistive_tech", "스크린리더"),
        ("assistive_tech", "화면확대"),
        ("education_level", "고졸"),
        ("career_years", "1"),
        ("experience_summary", ""),
        ("consent_sensitive", "1"),
    ], follow_redirects=False)
    assert r.status_code == 303
    assert "success" in r.headers["location"]

    conn = get_sqlite()
    p = conn.execute("SELECT * FROM seeker_profiles WHERE user_id=(SELECT id FROM users WHERE username='seeker1')").fetchone()
    conn.close()
    assert p["mobility_type"] == "대중교통"
    assert p["commute_max_minutes"] == 60
    comm = json.loads(p["communication_pref"])
    assert "문자" in comm
    assert "수어" in comm
    at = json.loads(p["assistive_tech"])
    assert "스크린리더" in at
    assert "화면확대" in at


def test_profile_v2_save_work_capacity(client):
    login(client, "seeker1")
    r = _post_form(client, "/profile", [
        ("disability_type_id", "1"),
        ("severity", "경증"),
        ("daily_work_hours", "6"),
        ("preferred_time", "오전"),
        ("rest_frequency", "2시간마다"),
        ("accommodation_needs", "휠체어접근"),
        ("accommodation_needs", "재택근무"),
        ("education_level", "고졸"),
        ("career_years", "0"),
        ("consent_sensitive", "1"),
    ], follow_redirects=False)
    assert r.status_code == 303
    assert "success" in r.headers["location"]

    conn = get_sqlite()
    p = conn.execute("SELECT * FROM seeker_profiles WHERE user_id=(SELECT id FROM users WHERE username='seeker1')").fetchone()
    conn.close()
    assert p["daily_work_hours"] == 6
    assert p["preferred_time"] == "오전"
    assert p["rest_frequency"] == "2시간마다"
    needs = json.loads(p["accommodation_needs"])
    assert "휠체어접근" in needs
    assert "재택근무" in needs


def test_profile_v2_save_education(client):
    login(client, "seeker1")
    r = client.post("/profile", data={
        "disability_type_id": 1,
        "severity": "경증",
        "education_level": "대졸",
        "school_name": "테스트대학교",
        "major": "컴퓨터공학",
        "career_years": 3,
        "recent_company": "테크회사",
        "recent_job_title": "개발자",
        "experience_summary": "3년차 개발자",
        "consent_sensitive": 1,
    }, follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    p = conn.execute("SELECT * FROM seeker_profiles WHERE user_id=(SELECT id FROM users WHERE username='seeker1')").fetchone()
    conn.close()
    assert p["education_level"] == "대졸"
    assert p["school_name"] == "테스트대학교"
    assert p["major"] == "컴퓨터공학"
    assert p["recent_company"] == "테크회사"
    assert p["recent_job_title"] == "개발자"
    assert p["experience_summary"] == "3년차 개발자"


def test_certifications_crud(client):
    login(client, "seeker1")
    # 자격증 2개 저장
    r = _post_form(client, "/profile", [
        ("disability_type_id", "1"),
        ("severity", "경증"),
        ("education_level", "고졸"),
        ("career_years", "0"),
        ("consent_sensitive", "1"),
        ("cert_name", "정보처리기사"),
        ("cert_date", "2024-06"),
        ("cert_org", "한국산업인력공단"),
        ("cert_name", "SQLD"),
        ("cert_date", "2024-09"),
        ("cert_org", "한국데이터산업진흥원"),
    ], follow_redirects=False)
    assert r.status_code == 303
    assert "success" in r.headers["location"]

    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    certs = conn.execute("SELECT * FROM seeker_certifications WHERE user_id=? ORDER BY id", (uid,)).fetchall()
    conn.close()
    assert len(certs) == 2
    assert certs[0]["cert_name"] == "정보처리기사"
    assert certs[1]["cert_name"] == "SQLD"

    # 자격증 1개로 재저장
    r = _post_form(client, "/profile", [
        ("disability_type_id", "1"),
        ("severity", "경증"),
        ("education_level", "고졸"),
        ("career_years", "0"),
        ("consent_sensitive", "1"),
        ("cert_name", "컴활2급"),
        ("cert_date", "2023-03"),
        ("cert_org", "대한상공회의소"),
    ], follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    certs = conn.execute("SELECT * FROM seeker_certifications WHERE user_id=? ORDER BY id", (uid,)).fetchall()
    conn.close()
    assert len(certs) == 1
    assert certs[0]["cert_name"] == "컴활2급"


def test_operator_sees_new_fields(client):
    login(client, "op1")
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.close()

    r = client.get(f"/op/seekers/{uid}")
    assert r.status_code == 200
    assert "이동수단" in r.text
    assert "보조기기" in r.text
    assert "최종학력" in r.text
    assert "자격증" in r.text
