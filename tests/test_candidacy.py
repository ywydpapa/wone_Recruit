from tests.conftest import login
from core.db import get_sqlite


def test_apply_form_renders(client):
    login(client, "seeker2")
    r = client.get("/apply/1")
    assert r.status_code == 200


def test_apply_submit(client):
    login(client, "seeker2")
    r = client.post("/apply/2", data={"cover_letter": "지원합니다"}, follow_redirects=False)
    assert r.status_code == 303
    conn = get_sqlite()
    cand = conn.execute("SELECT * FROM candidacies WHERE seeker_user_id=? AND job_id=2",
                        (client.cookies.get("session") and 4,)).fetchone()
    conn.close()


def test_apply_duplicate_blocked(client):
    login(client, "seeker1")
    # seeker1은 시드에서 job 1에 이미 지원
    r = client.post("/apply/1", data={"cover_letter": "다시 지원"}, follow_redirects=False)
    assert r.status_code == 303


def test_applications_list(client):
    login(client, "seeker1")
    r = client.get("/applications")
    assert r.status_code == 200


def test_withdraw(client):
    login(client, "seeker1")
    conn = get_sqlite()
    cand = conn.execute("SELECT id FROM candidacies WHERE seeker_user_id=(SELECT id FROM users WHERE username='seeker1') LIMIT 1").fetchone()
    conn.close()
    if cand:
        r = client.post(f"/applications/{cand['id']}/withdraw", follow_redirects=False)
        assert r.status_code == 303


def test_company_applicants_list(client):
    login(client, "comp1")
    r = client.get("/company/jobs/1/applicants")
    assert r.status_code == 200


def test_company_applicant_detail(client):
    login(client, "comp1")
    conn = get_sqlite()
    cand = conn.execute("SELECT id FROM candidacies WHERE job_id=1 LIMIT 1").fetchone()
    conn.close()
    if cand:
        r = client.get(f"/company/jobs/1/applicants/{cand['id']}")
        assert r.status_code == 200


def test_company_status_change(client):
    login(client, "comp1")
    conn = get_sqlite()
    cand = conn.execute("SELECT id FROM candidacies WHERE job_id=1 AND status='pending' LIMIT 1").fetchone()
    conn.close()
    if cand:
        r = client.post(f"/company/jobs/1/applicants/{cand['id']}/status",
                        data={"status": "reviewing", "comment": "검토합니다"},
                        follow_redirects=False)
        assert r.status_code == 303


def test_candidacy_transition_logic():
    from core.candidacy import can_transition
    assert can_transition("pending", "reviewing")
    assert can_transition("pending", "rejected")
    assert not can_transition("pending", "hired")
    assert not can_transition("hired", "reviewing")
    assert not can_transition("withdrawn", "pending")
