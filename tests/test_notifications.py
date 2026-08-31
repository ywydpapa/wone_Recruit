from tests.conftest import login


def test_notification_count_api(client):
    r = client.get("/api/notifications/count")
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_notifications_page(client):
    login(client, "seeker1")
    r = client.get("/notifications")
    assert r.status_code == 200
    assert "알림" in r.text


def test_notification_count_after_read(client):
    login(client, "seeker1")
    from core.db import get_sqlite
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()
    conn.execute(
        "INSERT INTO notifications (user_id, message, link) VALUES (?,?,?)",
        (seeker["id"], "test notification", "/"),
    )
    conn.commit()
    conn.close()
    r = client.get("/api/notifications/count")
    assert r.json()["count"] == 1
    client.get("/notifications")
    r = client.get("/api/notifications/count")
    assert r.json()["count"] == 0


def test_notification_on_apply(client):
    login(client, "seeker1")
    # seeker1은 job 1에 이미 지원, job 2로 테스트
    from core.db import get_sqlite
    conn = get_sqlite()
    job2 = conn.execute("SELECT id FROM job_postings ORDER BY id LIMIT 1 OFFSET 1").fetchone()
    comp_user = conn.execute("SELECT id FROM users WHERE username='comp1'").fetchone()
    conn.close()
    if job2:
        client.post(f"/apply/{job2['id']}", data={"cover_letter": "test"}, follow_redirects=False)
        conn = get_sqlite()
        notifs = conn.execute(
            "SELECT * FROM notifications WHERE user_id=?", (comp_user["id"],)
        ).fetchall()
        conn.close()
        assert len(notifs) >= 1


def test_notification_requires_login(client):
    r = client.get("/notifications", follow_redirects=False)
    assert r.status_code == 303
