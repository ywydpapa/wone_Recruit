from tests.conftest import login
from core.db import get_sqlite


def uid(username):
    conn = get_sqlite()
    row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return row["id"]


def test_consult_create_notifies_operator(client):
    login(client, "seeker1")
    r = client.post(
        "/consult",
        data={"category": "job", "content": "면접 준비가 어렵습니다.", "method": "phone", "preferred_time": "평일 오후"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/consult"

    conn = get_sqlite()
    req = conn.execute("SELECT * FROM consult_requests WHERE seeker_user_id=?", (uid("seeker1"),)).fetchone()
    assert req is not None
    assert req["content"] == "면접 준비가 어렵습니다."
    op_id = uid("op1")
    noti = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND kind='consult'", (op_id,)
    ).fetchone()
    conn.close()
    assert noti is not None
    assert noti["link"] == f"/op/seekers/{uid('seeker1')}"


def test_consult_notifies_manager(client):
    seeker_id = uid("seeker1")
    manager_id = uid("counsel1")
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO manager_assignments (manager_user_id, seeker_user_id, assigned_by) VALUES (?,?,?)",
        (manager_id, seeker_id, uid("op1")),
    )
    conn.commit()
    conn.close()

    login(client, "seeker1")
    r = client.post(
        "/consult",
        data={"category": "device", "content": "보조기기 지원이 필요합니다.", "method": "video", "preferred_time": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303

    conn = get_sqlite()
    req = conn.execute(
        "SELECT id FROM consult_requests WHERE seeker_user_id=?", (seeker_id,)
    ).fetchone()
    noti = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND kind='consult'", (manager_id,)
    ).fetchone()
    op_noti = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND kind='consult'", (uid("op1"),)
    ).fetchone()
    conn.close()
    assert noti is not None
    assert noti["link"] == f"/mgr/consult-requests/{req['id']}"
    assert op_noti is None


def test_consult_validation_error(client):
    login(client, "seeker1")
    r = client.post(
        "/consult",
        data={"category": "job", "content": "  ", "method": "phone", "preferred_time": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "error=content_required" in r.headers["location"]

    conn = get_sqlite()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM consult_requests WHERE seeker_user_id=?", (uid("seeker1"),)
    ).fetchone()[0]
    conn.close()
    assert cnt == 0


def test_consult_cancel_own_pending(client):
    login(client, "seeker1")
    client.post(
        "/consult",
        data={"category": "job", "content": "취소할 상담입니다.", "method": "phone", "preferred_time": ""},
        follow_redirects=False,
    )
    conn = get_sqlite()
    req = conn.execute(
        "SELECT id FROM consult_requests WHERE seeker_user_id=?", (uid("seeker1"),)
    ).fetchone()
    conn.close()

    r = client.post(f"/consult/{req['id']}/cancel", follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    row = conn.execute("SELECT status FROM consult_requests WHERE id=?", (req["id"],)).fetchone()
    conn.close()
    assert row["status"] == "cancelled"


def test_consult_cancel_denied_for_other_seeker(client):
    login(client, "seeker1")
    client.post(
        "/consult",
        data={"category": "job", "content": "다른 사람 상담입니다.", "method": "phone", "preferred_time": ""},
        follow_redirects=False,
    )
    conn = get_sqlite()
    req = conn.execute(
        "SELECT id FROM consult_requests WHERE seeker_user_id=?", (uid("seeker1"),)
    ).fetchone()
    conn.close()

    login(client, "seeker2")
    client.post(f"/consult/{req['id']}/cancel", follow_redirects=False)

    conn = get_sqlite()
    row = conn.execute("SELECT status FROM consult_requests WHERE id=?", (req["id"],)).fetchone()
    conn.close()
    assert row["status"] == "pending"


def test_consult_list_shows_hotlines(client):
    login(client, "seeker1")
    r = client.get("/consult")
    assert "1588-1519" in r.text


def test_consult_list_hides_notes(client):
    seeker_id = uid("seeker1")
    manager_id = uid("counsel1")
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO consultation_sessions "
        "(seeker_user_id, manager_user_id, session_type, scheduled_at, method, location, status, notes) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (seeker_id, manager_id, "career_counseling", "2026-10-05T14:00", "video", "", "scheduled", "비공개 메모입니다"),
    )
    conn.commit()
    conn.close()

    login(client, "seeker1")
    r = client.get("/consult")
    assert r.status_code == 200
    assert "진로 상담" in r.text
    assert "비공개 메모입니다" not in r.text


def test_dash_no_consult_req(client):
    login(client, "seeker1")
    r = client.get("/")
    assert "/request-consultation" not in r.text
