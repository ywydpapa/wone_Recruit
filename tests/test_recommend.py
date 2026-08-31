import json
from core.db import get_sqlite
from core.dashboard_data import get_recommended_jobs
from tests.conftest import login


def test_recommended_jobs_returns_results(client):
    login(client, "seeker1")
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    results = get_recommended_jobs(conn, uid)
    conn.close()
    assert len(results) > 0


def test_recommended_jobs_have_match_score(client):
    login(client, "seeker1")
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    results = get_recommended_jobs(conn, uid)
    conn.close()
    for r in results:
        assert "match_score" in r
        assert "match_count" in r
        assert "total_needs" in r
        assert r["job"] is not None


def test_recommended_excludes_applied_jobs(client):
    login(client, "seeker1")
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    # seeker1은 시드에서 job 1에 이미 지원
    applied_job_ids = set(
        r["job_id"] for r in conn.execute(
            "SELECT job_id FROM candidacies WHERE seeker_user_id=?", (uid,)
        ).fetchall()
    )
    results = get_recommended_jobs(conn, uid)
    conn.close()
    for r in results:
        assert r["job"]["id"] not in applied_job_ids


def test_recommended_sorted_by_score(client):
    login(client, "seeker1")
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    results = get_recommended_jobs(conn, uid)
    conn.close()
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i]["match_score"] >= results[i + 1]["match_score"]


def test_recommended_on_dashboard(client):
    login(client, "seeker1")
    r = client.get("/")
    assert r.status_code == 200
    assert "맞춤 공고" in r.text


def test_no_profile_no_recommendations(client):
    login(client, "seeker1")
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.execute("DELETE FROM seeker_profiles WHERE user_id=?", (uid,))
    conn.commit()
    results = get_recommended_jobs(conn, uid)
    conn.close()
    assert results == []
