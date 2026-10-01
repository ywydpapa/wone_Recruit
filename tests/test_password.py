from core.security import check_password
from tests.conftest import login


def test_password_change_page(client):
    login(client, "seeker1")
    r = client.get("/account/password")
    assert r.status_code == 200
    assert "비밀번호 변경" in r.text


def test_password_change_success(client):
    login(client, "seeker1")
    r = client.post("/account/password", data={
        "current_password": "admin1234",
        "new_password": "newpass12345",
        "confirm_password": "newpass12345",
    }, follow_redirects=False)
    assert r.status_code == 303
    client.get("/logout")
    login(client, "seeker1", "newpass12345")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200


def test_password_change_wrong_current(client):
    login(client, "seeker1")
    r = client.post("/account/password", data={
        "current_password": "wrongpass",
        "new_password": "newpass12345",
        "confirm_password": "newpass12345",
    }, follow_redirects=True)
    assert "일치하지 않습니다" in r.text


def test_password_change_mismatch(client):
    login(client, "seeker1")
    r = client.post("/account/password", data={
        "current_password": "admin1234",
        "new_password": "newpass12345",
        "confirm_password": "different999",
    }, follow_redirects=True)
    assert "일치하지 않습니다" in r.text


def test_password_change_requires_login(client):
    r = client.get("/account/password", follow_redirects=False)
    assert r.status_code == 303


def test_operator_reset_password(client):
    login(client, "op1")
    from core.db import get_sqlite
    conn = get_sqlite()
    row = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()
    conn.close()
    uid = row["id"]
    r = client.post(f"/op/users/{uid}/reset-password", data={
        "new_password": "reset1234567",
    }, follow_redirects=False)
    assert r.status_code == 303
    client.get("/logout")
    r = login(client, "seeker1", "reset1234567")
    assert r.headers["location"] == "/change-password"


def test_password_policy():
    assert check_password("abc12345") == "short"
    assert check_password("abcdefghijkl") == "weak"
    assert check_password("123456789012") == "weak"
    assert check_password("Password1234") == "common"
    assert check_password("aaaa1111aaaa") == "common"
    assert check_password("haneul0512kim") is None
    assert check_password("haneul 0512kim") == "space"
    assert check_password("하늘haneul0512") == "charset"


def test_password_change_weak(client):
    login(client, "seeker1")
    r = client.post("/account/password", data={
        "current_password": "admin1234",
        "new_password": "onlyletterspw",
        "confirm_password": "onlyletterspw",
    }, follow_redirects=False)
    assert "error=weak" in r.headers["location"]


def test_operator_reset_password_policy(client):
    login(client, "op1")
    from core.db import get_sqlite
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.close()
    r = client.post(f"/op/users/{uid}/reset-password", data={"new_password": "reset12345"}, follow_redirects=False)
    assert r.headers["location"] == f"/op/seekers/{uid}?pw_error=short"
