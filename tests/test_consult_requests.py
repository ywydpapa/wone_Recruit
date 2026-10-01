from tests.conftest import login
from core.db import get_sqlite
from core.security import hash_password


def uid(username):
    conn = get_sqlite()
    row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return row["id"]


def assign(manager_id, seeker_id, by_id):
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO manager_assignments (manager_user_id, seeker_user_id, assigned_by) VALUES (?,?,?)",
        (manager_id, seeker_id, by_id),
    )
    conn.commit()
    conn.close()


def make_req(seeker_id, content, category="job", method="phone", preferred_time=""):
    conn = get_sqlite()
    cur = conn.execute(
        "INSERT INTO consult_requests (seeker_user_id, category, content, method, preferred_time) "
        "VALUES (?,?,?,?,?)",
        (seeker_id, category, content, method, preferred_time),
    )
    req_id = cur.lastrowid
    conn.commit()
    conn.close()
    return req_id


def make_manager(username, name="다른매니저"):
    conn = get_sqlite()
    cur = conn.execute(
        "INSERT INTO users (username, password, name, phone, role) VALUES (?,?,?,?,'manager')",
        (username, hash_password("admin1234"), name, "010-0000-0000"),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def test_inbox_shows_only_assigned_seekers(client):
    seeker1 = uid("seeker1")
    seeker2 = uid("seeker2")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker1, op_id)
    make_req(seeker1, "면접이 걱정됩니다")
    make_req(seeker2, "다른 매니저 요청입니다")

    login(client, "counsel1")
    r = client.get("/mgr/consult-requests")
    assert r.status_code == 200
    assert "면접이 걱정됩니다" in r.text
    assert "다른 매니저 요청입니다" not in r.text


def test_accept_transitions_and_notifies_seeker(client):
    seeker1 = uid("seeker1")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker1, op_id)
    req_id = make_req(seeker1, "상담을 신청합니다")

    login(client, "counsel1")
    r = client.post(f"/mgr/consult-requests/{req_id}/accept", follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    row = conn.execute("SELECT * FROM consult_requests WHERE id=?", (req_id,)).fetchone()
    noti = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND kind='consult' ORDER BY id DESC LIMIT 1",
        (seeker1,),
    ).fetchone()
    conn.close()
    assert row["status"] == "accepted"
    assert row["manager_user_id"] == manager_id
    assert row["handled_at"] is not None
    assert noti is not None
    assert noti["link"] == "/consult"
    assert "확인" in noti["message"]


def test_reply_transitions_and_notifies_seeker(client):
    seeker1 = uid("seeker1")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker1, op_id)
    req_id = make_req(seeker1, "답변이 필요합니다")

    login(client, "counsel1")
    r = client.post(
        f"/mgr/consult-requests/{req_id}/reply",
        data={"reply": "요청하신 내용은 이렇게 안내드립니다."},
        follow_redirects=False,
    )
    assert r.status_code == 303

    conn = get_sqlite()
    row = conn.execute("SELECT * FROM consult_requests WHERE id=?", (req_id,)).fetchone()
    noti = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND kind='consult' ORDER BY id DESC LIMIT 1",
        (seeker1,),
    ).fetchone()
    conn.close()
    assert row["status"] == "done"
    assert row["reply"] == "요청하신 내용은 이렇게 안내드립니다."
    assert noti is not None
    assert noti["link"] == "/consult"


def test_other_manager_gets_404(client):
    seeker1 = uid("seeker1")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker1, op_id)
    req_id = make_req(seeker1, "다른 매니저는 못 봅니다")
    make_manager("counsel2")

    login(client, "counsel2")
    r = client.get(f"/mgr/consult-requests/{req_id}")
    assert r.status_code == 404

    r = client.post(f"/mgr/consult-requests/{req_id}/accept", follow_redirects=False)
    assert r.status_code == 404

    r = client.post(f"/mgr/consult-requests/{req_id}/reply", data={"reply": "몰래 답변"}, follow_redirects=False)
    assert r.status_code == 404


def test_schedule_links_session(client):
    seeker1 = uid("seeker1")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker1, op_id)
    req_id = make_req(seeker1, "일정을 잡고 싶습니다", method="video")

    login(client, "counsel1")
    r = client.get(f"/mgr/consultations/new?seeker_id={seeker1}&request_id={req_id}")
    assert r.status_code == 200
    assert 'name="request_id" value="{}"'.format(req_id) in r.text

    r = client.post(
        "/mgr/consultations",
        data={
            "seeker_id": seeker1,
            "session_type": "career_counseling",
            "scheduled_at": "2026-10-10T10:00",
            "method": "video",
            "location": "",
            "notes": "",
            "request_id": req_id,
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    conn = get_sqlite()
    row = conn.execute("SELECT * FROM consult_requests WHERE id=?", (req_id,)).fetchone()
    session = conn.execute(
        "SELECT * FROM consultation_sessions WHERE seeker_user_id=? ORDER BY id DESC LIMIT 1", (seeker1,)
    ).fetchone()
    noti = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND kind='consult' ORDER BY id DESC LIMIT 1",
        (seeker1,),
    ).fetchone()
    conn.close()
    assert row["status"] == "scheduled"
    assert row["session_id"] == session["id"]
    assert row["manager_user_id"] == manager_id
    assert noti is not None
    assert "일정" in noti["message"]


def test_completing_session_marks_request_done(client):
    seeker1 = uid("seeker1")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker1, op_id)
    req_id = make_req(seeker1, "완료될 상담입니다")

    login(client, "counsel1")
    client.post(
        "/mgr/consultations",
        data={
            "seeker_id": seeker1,
            "session_type": "career_counseling",
            "scheduled_at": "2026-10-10T10:00",
            "method": "video",
            "location": "",
            "notes": "",
            "request_id": req_id,
        },
        follow_redirects=False,
    )
    conn = get_sqlite()
    session = conn.execute(
        "SELECT * FROM consultation_sessions WHERE seeker_user_id=? ORDER BY id DESC LIMIT 1", (seeker1,)
    ).fetchone()
    conn.close()

    r = client.post(
        f"/mgr/consultations/{session['id']}/complete",
        data={"seeker_id": seeker1},
        follow_redirects=False,
    )
    assert r.status_code == 303

    conn = get_sqlite()
    row = conn.execute("SELECT status FROM consult_requests WHERE id=?", (req_id,)).fetchone()
    sess_row = conn.execute("SELECT status FROM consultation_sessions WHERE id=?", (session["id"],)).fetchone()
    conn.close()
    assert sess_row["status"] == "completed"
    assert row["status"] == "done"
