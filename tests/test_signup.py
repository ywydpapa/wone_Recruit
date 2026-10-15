import pytest

from core.db import get_sqlite
from core.rate_limit import _store


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr("routers.auth.send_mail", lambda to, subject, body: sent.append((to, body)) or True)
    _store.clear()
    return sent


def test_signup_bad_id(client):
    r = client.post("/signup", data={
        "username": "Bad_Id!", "password": "testpass1234", "confirm_password": "testpass1234",
        "name": "홍길동", "phone": "", "email": "hong@example.com", "role": "seeker",
        "agree_terms": "1", "agree_privacy": "1", "agree_age": "1",
    }, follow_redirects=False)
    assert r.status_code == 400
    assert "홍길동" in r.text
    assert "hong@example.com" in r.text


def test_signup_phone(client):
    r = client.post("/signup", data={
        "username": "phoneuser", "password": "testpass1234", "confirm_password": "testpass1234",
        "name": "전화테스트", "phone": "01011112222", "email": "phone@example.com", "role": "seeker",
        "agree_terms": "1", "agree_privacy": "1", "agree_age": "1",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login?joined=1")
    conn = get_sqlite()
    row = conn.execute("SELECT phone FROM users WHERE username='phoneuser'").fetchone()
    conn.close()
    assert row["phone"] == "010-1111-2222"


def test_username_check(client):
    r = client.get("/api/usernames/seeker1")
    assert r.json() == {"valid": True, "available": False}
    r = client.get("/api/usernames/brandnewid")
    assert r.json() == {"valid": True, "available": True}
    r = client.get("/api/usernames/Bad_Id")
    assert r.json()["valid"] is False


def test_find_id(client, outbox):
    r = client.post("/find-id", data={"name": "김하늘", "email": "seeker1@example.com"}, follow_redirects=False)
    assert r.headers["location"] == "/find-id?sent=1"
    assert outbox[0][0] == "seeker1@example.com"
    assert "seeker1" in outbox[0][1]


def test_find_id_no_match(client, outbox):
    r = client.post("/find-id", data={"name": "없는사람", "email": "nobody@example.com"}, follow_redirects=False)
    assert r.headers["location"] == "/find-id?sent=1"
    assert outbox == []


def _company_form(**overrides):
    base = {
        "username": "compuser", "password": "testpass1234", "confirm_password": "testpass1234",
        "name": "김철수", "phone": "010-1234-5678", "email": "biz@example.com", "role": "company",
        "company_name": "테스트기업", "biz_no": "123-45-67891",
        "agree_terms": "1", "agree_privacy": "1", "agree_age": "1",
    }
    base.update(overrides)
    return base


def test_company_signup(client):
    r = client.post("/signup", data=_company_form(), follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login?joined=1")
    conn = get_sqlite()
    user = conn.execute("SELECT id, role FROM users WHERE username='compuser'").fetchone()
    company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["id"],)).fetchone()
    conn.close()
    assert user["role"] == "company"
    assert company["company_name"] == "테스트기업"
    assert company["biz_no"] == "123-45-67891"
    assert company["approval_status"] == "pending"


def test_company_no_name(client):
    r = client.post("/signup", data=_company_form(company_name=""), follow_redirects=False)
    assert r.status_code == 400
    assert "회사명을 입력" in r.text
    assert "김철수" in r.text
    assert "010-1234-5678" in r.text


def test_bizno_checksum(client):
    r = client.post("/signup", data=_company_form(biz_no="123-45-67890"), follow_redirects=False)
    assert r.status_code == 400
    assert "사업자등록번호 10자리" in r.text
    assert "김철수" in r.text


def test_company_no_phone(client):
    r = client.post("/signup", data=_company_form(phone=""), follow_redirects=False)
    assert r.status_code == 400
    assert "담당자 연락처를 입력" in r.text
    assert "테스트기업" in r.text


def test_bizno_dup(client):
    r = client.post("/signup", data=_company_form(), follow_redirects=False)
    assert r.status_code == 303
    r = client.post("/signup", data=_company_form(username="compuser2", email="biz2@example.com", biz_no="1234567891"), follow_redirects=False)
    assert r.status_code == 400
    assert "이미 가입된 사업자등록번호" in r.text


def test_bizno_closed(client, monkeypatch):
    async def fake_check(biz_no):
        return False
    monkeypatch.setattr("routers.auth.check_bizno", fake_check)
    r = client.post("/signup", data=_company_form(), follow_redirects=False)
    assert r.status_code == 400
    assert "휴업 또는 폐업" in r.text


def test_signup_company_tab(client):
    r = client.get("/signup?type=company")
    assert 'name="company_name"' in r.text
    assert 'name="biz_no"' in r.text


def test_signup_seeker_tab(client):
    r = client.get("/signup")
    assert 'name="company_name"' not in r.text
    assert 'name="biz_no"' not in r.text
