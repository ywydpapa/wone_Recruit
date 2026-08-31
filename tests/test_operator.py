from tests.conftest import login
from core.db import get_sqlite


def test_op_seekers_list(client):
    login(client, "op1")
    r = client.get("/op/seekers")
    assert r.status_code == 200


def test_op_seeker_detail(client):
    login(client, "op1")
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE role='seeker' LIMIT 1").fetchone()
    conn.close()
    r = client.get(f"/op/seekers/{seeker['id']}")
    assert r.status_code == 200


def test_op_seeker_detail_logs_access(client):
    login(client, "op1")
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE role='seeker' LIMIT 1").fetchone()
    conn.close()
    client.get(f"/op/seekers/{seeker['id']}")
    conn = get_sqlite()
    log = conn.execute("SELECT * FROM access_log WHERE seeker_user_id=?", (seeker['id'],)).fetchone()
    conn.close()
    assert log is not None


def test_op_companies_list(client):
    login(client, "op1")
    r = client.get("/op/companies")
    assert r.status_code == 200


def test_op_jobs_list(client):
    login(client, "op1")
    r = client.get("/op/jobs")
    assert r.status_code == 200


def test_op_matching_no_job(client):
    login(client, "op1")
    r = client.get("/op/matching")
    assert r.status_code == 200


def test_op_matching_with_job(client):
    login(client, "op1")
    r = client.get("/op/matching?job_id=2")
    assert r.status_code == 200


def test_op_propose(client):
    login(client, "op1")
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE username='seeker2'").fetchone()
    conn.close()
    r = client.post("/op/matching/propose", data={
        "job_id": 3,
        "seeker_user_id": seeker["id"],
    }, follow_redirects=False)
    assert r.status_code == 303


def test_seeker_proposals(client):
    # 운영자로 제안 생성
    login(client, "op1")
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE username='seeker2'").fetchone()
    conn.close()
    client.post("/op/matching/propose", data={
        "job_id": 3, "seeker_user_id": seeker["id"],
    }, follow_redirects=False)
    # 구직자로 확인
    client.get("/logout")
    login(client, "seeker2")
    r = client.get("/proposals")
    assert r.status_code == 200


def test_seeker_accept_proposal(client):
    login(client, "op1")
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE username='seeker2'").fetchone()
    conn.close()
    client.post("/op/matching/propose", data={
        "job_id": 3, "seeker_user_id": seeker["id"],
    }, follow_redirects=False)
    conn = get_sqlite()
    cand = conn.execute("SELECT id FROM candidacies WHERE seeker_user_id=? AND job_id=3",
                        (seeker["id"],)).fetchone()
    conn.close()
    client.get("/logout")
    login(client, "seeker2")
    if cand:
        r = client.post(f"/proposals/{cand['id']}/respond",
                        data={"action": "accept"}, follow_redirects=False)
        assert r.status_code == 303


def test_op_requires_operator_role(client):
    login(client, "seeker1")
    r = client.get("/op/seekers", follow_redirects=False)
    assert r.status_code in (303, 403)
