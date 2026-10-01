from tests.conftest import login
from core.db import get_sqlite


def uid(username):
    conn = get_sqlite()
    row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return row["id"]


def make_placement(seeker, job_id=2, company_id=1, status="active"):
    conn = get_sqlite()
    cur = conn.execute(
        """INSERT INTO candidacies (job_id, seeker_user_id, source, status)
           VALUES (?,?,?,'hired')""",
        (job_id, seeker, "direct"),
    )
    cand_id = cur.lastrowid
    cur = conn.execute(
        """INSERT INTO placements (candidacy_id, job_id, seeker_user_id, company_id, start_date, status)
           VALUES (?,?,?,?,'2026-01-05',?)""",
        (cand_id, job_id, seeker, company_id, status),
    )
    place_id = cur.lastrowid
    conn.execute(
        """INSERT INTO placement_followups (placement_id, followup_type, due_date, status, notes)
           VALUES (?,'1w','2026-01-12','completed','면담 내용 비공개 메모')""",
        (place_id,),
    )
    conn.execute(
        """INSERT INTO placement_followups (placement_id, followup_type, due_date, status)
           VALUES (?,'1m','2026-02-05','pending')""",
        (place_id,),
    )
    conn.commit()
    conn.close()
    return place_id


def test_status_page_renders_with_tiles(client):
    login(client, "seeker1")
    r = client.get("/status")
    assert r.status_code == 200
    assert "신청현황" in r.text
    assert "지원 진행중" in r.text
    assert "면접 예정" in r.text
    assert "받은 제안" in r.text
    assert "상담 진행중" in r.text


def test_app_tile_in_progress(client):
    seeker = uid("seeker1")
    conn = get_sqlite()
    job2 = conn.execute("SELECT id FROM job_postings ORDER BY id LIMIT 1 OFFSET 1").fetchone()["id"]
    conn.execute(
        "INSERT INTO candidacies (job_id, seeker_user_id, source, status) VALUES (?,?,'direct','reviewing')",
        (job2, seeker),
    )
    conn.commit()
    conn.close()

    login(client, "seeker1")
    r = client.get("/status")
    assert r.status_code == 200
    # 시드 candidacy(pending) 1건과 방금 추가한 reviewing 1건을 합쳐 진행중 2건임
    assert "지원 진행중 <strong>2</strong>" in r.text


def test_placement_followups(client):
    seeker = uid("seeker1")
    make_placement(seeker)

    login(client, "seeker1")
    r = client.get("/status")
    assert r.status_code == 200
    assert "채용연계" in r.text
    assert "1주차" in r.text
    assert "1개월차" in r.text
    assert "면담 내용 비공개 메모" not in r.text


def test_consult_hides_notes(client):
    seeker = uid("seeker1")
    manager = uid("counsel1")
    conn = get_sqlite()
    conn.execute(
        """INSERT INTO consult_requests (seeker_user_id, category, content, method, status)
           VALUES (?,'job','면접 준비 관련 상담 요청','phone','pending')""",
        (seeker,),
    )
    conn.execute(
        """INSERT INTO consultation_sessions (seeker_user_id, manager_user_id, session_type, notes, scheduled_at, method, status)
           VALUES (?,?,'career_counseling','절대 노출되면 안되는 상담 메모','2027-01-10 10:00:00','video','scheduled')""",
        (seeker, manager),
    )
    conn.commit()
    conn.close()

    login(client, "seeker1")
    r = client.get("/status")
    assert r.status_code == 200
    assert "취업 상담" in r.text
    assert "진로 상담" in r.text
    assert "절대 노출되면 안되는 상담 메모" not in r.text


def test_other_seeker_data_not_shown(client):
    seeker2 = uid("seeker2")
    make_placement(seeker2)
    conn = get_sqlite()
    conn.execute(
        """INSERT INTO consult_requests (seeker_user_id, category, content, method, status)
           VALUES (?,'device','보조기기 상담','phone','pending')""",
        (seeker2,),
    )
    conn.commit()
    conn.close()

    login(client, "seeker1")
    r = client.get("/status")
    assert r.status_code == 200
    assert "보조장비" not in r.text
    assert "아직 채용이 확정된 건이 없습니다" in r.text


def test_non_seeker_blocked(client):
    login(client, "comp1")
    r = client.get("/status")
    assert r.status_code == 403

    login(client, "op1")
    r = client.get("/status")
    assert r.status_code == 403
