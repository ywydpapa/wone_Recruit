from core.db import get_sqlite
from tests.conftest import login


def test_applications_page_shows_timeline(client):
    login(client, "seeker1")
    r = client.get("/applications")
    assert r.status_code == 200
    assert "status-timeline" in r.text


def test_timeline_shows_pending_step(client):
    login(client, "seeker1")
    r = client.get("/applications")
    assert r.status_code == 200
    assert "timeline-step" in r.text
    assert "timeline-dot" in r.text


def test_timeline_shows_status_labels(client):
    login(client, "seeker1")
    r = client.get("/applications")
    assert r.status_code == 200
    # 상태 라벨: pending=접수, reviewing=검토중 등
    assert "접수" in r.text


def test_timeline_with_status_change(client):
    login(client, "seeker1")
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    cand = conn.execute(
        "SELECT id FROM candidacies WHERE seeker_user_id=? LIMIT 1", (uid,)
    ).fetchone()
    conn.execute(
        "UPDATE candidacies SET status='reviewing' WHERE id=?", (cand["id"],)
    )
    conn.execute(
        """INSERT INTO status_history (candidacy_id, from_status, to_status, actor_id, comment)
           VALUES (?, 'pending', 'reviewing', ?, '서류 검토 시작')""",
        (cand["id"], uid),
    )
    conn.commit()
    conn.close()

    r = client.get("/applications")
    assert r.status_code == 200
    assert "검토중" in r.text


def test_applications_card_layout(client):
    login(client, "seeker1")
    r = client.get("/applications")
    assert r.status_code == 200
    assert "content-card" in r.text
    assert "사무지원" in r.text  # 첫번째 시드 공고 제목
    assert "한빛테크" in r.text
