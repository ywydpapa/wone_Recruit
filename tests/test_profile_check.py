import json
from core.db import get_sqlite
from tests.conftest import login


def test_apply_blocked_without_profile(client):
    login(client, "seeker1")
    # seeker1 프로필 삭제하여 미완성 상태 시뮬레이션
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.execute("DELETE FROM seeker_profiles WHERE user_id=?", (uid,))
    conn.commit()
    job_id = conn.execute("SELECT id FROM job_postings WHERE status='open' LIMIT 1").fetchone()["id"]
    conn.close()

    r = client.get(f"/apply/{job_id}", follow_redirects=False)
    assert r.status_code == 303
    assert "incomplete" in r.headers["location"]


def test_apply_blocked_missing_disability_type(client):
    login(client, "seeker1")
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.execute("UPDATE seeker_profiles SET disability_type_id=NULL WHERE user_id=?", (uid,))
    conn.commit()
    job_id = conn.execute("SELECT id FROM job_postings WHERE status='open' LIMIT 1").fetchone()["id"]
    conn.close()

    r = client.get(f"/apply/{job_id}", follow_redirects=False)
    assert r.status_code == 303
    assert "incomplete" in r.headers["location"]


def test_apply_blocked_missing_accommodation(client):
    login(client, "seeker1")
    conn = get_sqlite()
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.execute("UPDATE seeker_profiles SET accommodation_needs='[]' WHERE user_id=?", (uid,))
    conn.commit()
    job_id = conn.execute("SELECT id FROM job_postings WHERE status='open' LIMIT 1").fetchone()["id"]
    conn.close()

    r = client.get(f"/apply/{job_id}", follow_redirects=False)
    assert r.status_code == 303
    assert "incomplete" in r.headers["location"]


def test_apply_allowed_with_complete_profile(client):
    login(client, "seeker1")
    conn = get_sqlite()
    job_id = conn.execute("SELECT id FROM job_postings WHERE status='open' LIMIT 1").fetchone()["id"]
    conn.close()
    r = client.get(f"/apply/{job_id}")
    assert r.status_code == 200
    assert "지원서 작성" in r.text


def test_profile_completeness_on_dashboard(client):
    login(client, "seeker1")
    r = client.get("/")
    assert r.status_code == 200
    assert "프로필 완성도" in r.text


def test_profile_incomplete_msg_shown(client):
    login(client, "seeker1")
    r = client.get("/profile?error=incomplete&msg=프로필을+먼저+완성해주세요.")
    assert r.status_code == 200
    assert "프로필을 먼저 완성해주세요" in r.text
