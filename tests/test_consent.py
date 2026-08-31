from core.db import get_sqlite
from tests.conftest import login


def test_consent_page_requires_login(client):
    r = client.get("/account/consent", follow_redirects=False)
    assert r.status_code in (303, 403)


def test_consent_page_loads(client):
    login(client, "seeker1")
    r = client.get("/account/consent")
    assert r.status_code == 200
    assert "개인정보 관리" in r.text


def test_withdraw_sensitive_consent(client):
    login(client, "seeker1")
    r = client.post("/account/consent/sensitive", data={
        "current_password": "admin1234",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "withdrawn" in r.headers["location"]

    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    profile = conn.execute(
        "SELECT consent_sensitive, disability_type_id, consent_withdrawn_at FROM seeker_profiles WHERE user_id=?",
        (uid,),
    ).fetchone()
    conn.close()
    assert profile["consent_sensitive"] == 0
    assert profile["disability_type_id"] is None
    assert profile["consent_withdrawn_at"] is not None


def test_withdraw_with_wrong_password_fails(client):
    login(client, "seeker1")
    r = client.post("/account/consent/sensitive", data={
        "current_password": "wrongpassword",
    }, follow_redirects=True)
    assert "일치하지 않습니다" in r.text

    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    profile = conn.execute(
        "SELECT consent_sensitive FROM seeker_profiles WHERE user_id=?", (uid,)
    ).fetchone()
    conn.close()
    assert profile["consent_sensitive"] == 1


def test_restore_sensitive_consent(client):
    login(client, "seeker1")
    client.post("/account/consent/sensitive", data={"current_password": "admin1234"}, follow_redirects=False)

    r = client.post("/account/consent/sensitive/restore", follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    profile = conn.execute(
        "SELECT consent_sensitive, consented_at, consent_withdrawn_at FROM seeker_profiles WHERE user_id=?",
        (uid,),
    ).fetchone()
    conn.close()
    assert profile["consent_sensitive"] == 1
    assert profile["consented_at"] is not None
    assert profile["consent_withdrawn_at"] is None


def test_toggle_marketing_consent(client):
    login(client, "seeker1")

    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    initial = conn.execute("SELECT agreed_marketing_at FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    initial_state = initial["agreed_marketing_at"]

    r = client.post("/account/consent/marketing", follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    after = conn.execute("SELECT agreed_marketing_at FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()

    if initial_state:
        assert after["agreed_marketing_at"] is None
    else:
        assert after["agreed_marketing_at"] is not None

    r = client.post("/account/consent/marketing", follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    after2 = conn.execute("SELECT agreed_marketing_at FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()

    if initial_state:
        assert after2["agreed_marketing_at"] is not None
    else:
        assert after2["agreed_marketing_at"] is None
