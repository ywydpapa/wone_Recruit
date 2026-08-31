from tests.conftest import login


def test_signup_seeker(client):
    r = client.post("/signup", data={
        "username": "new_seeker", "password": "testpass1234",
        "name": "테스트", "phone": "010-0000-0000", "role": "seeker",
        "agree_terms": "1", "agree_privacy": "1",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_signup_company(client):
    r = client.post("/signup", data={
        "username": "new_comp", "password": "testpass1234",
        "name": "테스트기업", "phone": "051-000-0000", "role": "company",
        "agree_terms": "1", "agree_privacy": "1",
    }, follow_redirects=False)
    assert r.status_code == 303


def test_signup_without_agree(client):
    r = client.post("/signup", data={
        "username": "no_agree", "password": "testpass1234",
        "name": "미동의", "phone": "", "role": "seeker",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "agree_required" in r.headers["location"]


def test_signup_operator_rejected(client):
    r = client.post("/signup", data={
        "username": "bad_op", "password": "testpass1234",
        "name": "해커", "phone": "", "role": "operator",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "error" in r.headers["location"]


def test_dashboard_seeker(client):
    login(client, "seeker1")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "구직자 대시보드" in r.text


def test_dashboard_company(client):
    login(client, "comp1")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "기업 대시보드" in r.text


def test_dashboard_operator(client):
    login(client, "op1")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "운영자 대시보드" in r.text


def test_withdraw_page_requires_login(client):
    r = client.get("/account/withdraw", follow_redirects=False)
    assert r.status_code == 303


def test_withdraw_with_correct_password(client):
    login(client, "seeker1")
    r = client.post("/account/withdraw", data={
        "current_password": "admin1234",
        "reason": "inactive",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "withdrawn=1" in r.headers["location"]


def test_withdraw_with_wrong_password(client):
    login(client, "seeker1")
    r = client.post("/account/withdraw", data={
        "current_password": "wrongpass",
        "reason": "",
    }, follow_redirects=True)
    assert "일치하지 않습니다" in r.text


def test_deleted_user_cannot_login(client):
    login(client, "seeker1")
    client.post("/account/withdraw", data={
        "current_password": "admin1234",
        "reason": "",
    }, follow_redirects=False)
    r = client.post("/login_check", data={
        "username": "seeker1", "password": "admin1234",
    }, follow_redirects=True)
    assert "탈퇴한 계정" in r.text
