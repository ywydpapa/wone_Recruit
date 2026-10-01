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
    # seeker1은 job 1에 이미 지원했으므로 job 2로 검증함
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


def test_disabled_kind_skipped(client):
    from core.db import get_sqlite
    from core.notifications import create_notification

    login(client, "seeker1")
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()
    conn.execute(
        "UPDATE users SET notify_settings=? WHERE id=?",
        ('{"proposal": false}', seeker["id"]),
    )
    conn.commit()
    create_notification(conn, seeker["id"], "매칭 제안 도착", "/proposals", kind="proposal")
    conn.commit()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND kind='proposal'", (seeker["id"],)
    ).fetchone()[0]
    conn.close()
    assert cnt == 0


def test_system_kind_never_skipped(client):
    from core.db import get_sqlite
    from core.notifications import create_notification

    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()
    conn.execute(
        "UPDATE users SET notify_settings=? WHERE id=?",
        ('{"system": false}', seeker["id"]),
    )
    conn.commit()
    create_notification(conn, seeker["id"], "공지사항", "/notices", kind="system")
    conn.commit()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND kind='system'", (seeker["id"],)
    ).fetchone()[0]
    conn.close()
    assert cnt == 1


def test_kind_filter(client):
    from core.db import get_sqlite
    from core.notifications import create_notification

    login(client, "seeker1")
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()
    create_notification(conn, seeker["id"], "면접 안내", "/applications", kind="interview")
    create_notification(conn, seeker["id"], "메시지 도착", "/messages/1", kind="message")
    conn.commit()
    conn.close()

    r = client.get("/notifications?kind=interview")
    assert r.status_code == 200
    assert "면접 안내" in r.text
    assert "메시지 도착" not in r.text


def test_only_shown_page_marked_read(client):
    from core.db import get_sqlite
    from core.notifications import create_notification

    login(client, "seeker1")
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()
    for i in range(25):
        create_notification(conn, seeker["id"], f"알림 {i}", "/", kind="system")
    conn.commit()
    conn.close()

    client.get("/notifications")
    conn = get_sqlite()
    unread = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (seeker["id"],)
    ).fetchone()[0]
    conn.close()
    assert unread == 5


def test_notify_settings_save(client):
    login(client, "seeker1")
    r = client.post("/account/notify", data={"apply": "on"}, follow_redirects=False)
    assert r.status_code == 303

    from core.db import get_sqlite
    import json

    conn = get_sqlite()
    seeker = conn.execute("SELECT id, notify_settings FROM users WHERE username='seeker1'").fetchone()
    conn.close()
    settings = json.loads(seeker["notify_settings"])
    assert settings["apply"] is True
    assert settings["message"] is False


def test_saved_search_notify(client):
    from core.db import get_sqlite
    from core.jobs import notify_saved_searches

    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()
    conn.execute(
        "INSERT INTO saved_searches (user_id, name, filters, last_checked_at) VALUES (?,?,?,?)",
        (seeker["id"], "전체", "{}", "2000-01-01 00:00:00"),
    )
    conn.commit()
    has_open = conn.execute("SELECT COUNT(*) FROM job_postings WHERE status='open'").fetchone()[0]
    conn.close()

    assert notify_saved_searches() == (1 if has_open else 0)
    # 이미 알린 공고는 다시 알리지 않음
    assert notify_saved_searches() == 0
