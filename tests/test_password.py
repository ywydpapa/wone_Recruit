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
        "new_password": "newpass1234",
        "confirm_password": "newpass1234",
    }, follow_redirects=False)
    assert r.status_code == 303
    client.get("/logout")
    login(client, "seeker1", "newpass1234")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200


def test_password_change_wrong_current(client):
    login(client, "seeker1")
    r = client.post("/account/password", data={
        "current_password": "wrongpass",
        "new_password": "newpass1234",
        "confirm_password": "newpass1234",
    }, follow_redirects=True)
    assert "일치하지 않습니다" in r.text


def test_password_change_mismatch(client):
    login(client, "seeker1")
    r = client.post("/account/password", data={
        "current_password": "admin1234",
        "new_password": "newpass1234",
        "confirm_password": "different99",
    }, follow_redirects=True)
    assert "서로 다릅니다" in r.text


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
        "new_password": "reset12345",
    }, follow_redirects=False)
    assert r.status_code == 303
    client.get("/logout")
    login(client, "seeker1", "reset12345")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
