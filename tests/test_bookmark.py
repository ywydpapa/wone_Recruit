from core.db import get_sqlite
from tests.conftest import login


def test_bookmark_toggle_add(client):
    login(client, "seeker1")
    job_id = get_sqlite().execute("SELECT id FROM job_postings LIMIT 1").fetchone()["id"]
    r = client.post(f"/bookmarks/{job_id}/toggle", follow_redirects=False)
    assert r.status_code == 303
    conn = get_sqlite()
    b = conn.execute("SELECT * FROM bookmarks WHERE job_id=?", (job_id,)).fetchone()
    conn.close()
    assert b is not None


def test_bookmark_toggle_remove(client):
    login(client, "seeker1")
    conn = get_sqlite()
    job_id = conn.execute("SELECT id FROM job_postings LIMIT 1").fetchone()["id"]
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.execute("INSERT INTO bookmarks (user_id, job_id) VALUES (?,?)", (uid, job_id))
    conn.commit()
    conn.close()
    r = client.post(f"/bookmarks/{job_id}/toggle", follow_redirects=False)
    assert r.status_code == 303
    conn = get_sqlite()
    b = conn.execute("SELECT * FROM bookmarks WHERE user_id=? AND job_id=?", (uid, job_id)).fetchone()
    conn.close()
    assert b is None


def test_bookmark_toggle_json(client):
    login(client, "seeker1")
    job_id = get_sqlite().execute("SELECT id FROM job_postings LIMIT 1").fetchone()["id"]
    r = client.post(f"/bookmarks/{job_id}/toggle", headers={"accept": "application/json"})
    assert r.status_code == 200
    assert r.json()["bookmarked"] is True


def test_bookmarks_page(client):
    login(client, "seeker1")
    conn = get_sqlite()
    job_id = conn.execute("SELECT id FROM job_postings LIMIT 1").fetchone()["id"]
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.execute("INSERT INTO bookmarks (user_id, job_id) VALUES (?,?)", (uid, job_id))
    conn.commit()
    conn.close()
    r = client.get("/bookmarks")
    assert r.status_code == 200
    assert "저장한 공고" in r.text


def test_bookmarks_empty(client):
    login(client, "seeker1")
    r = client.get("/bookmarks")
    assert r.status_code == 200
    assert "저장한 공고가 없습니다" in r.text


def test_bookmark_requires_login(client):
    r = client.get("/bookmarks", follow_redirects=False)
    assert r.status_code in (303, 403)


def test_bookmark_count_on_dashboard(client):
    login(client, "seeker1")
    conn = get_sqlite()
    job_id = conn.execute("SELECT id FROM job_postings LIMIT 1").fetchone()["id"]
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.execute("INSERT INTO bookmarks (user_id, job_id) VALUES (?,?)", (uid, job_id))
    conn.commit()
    conn.close()
    r = client.get("/")
    assert r.status_code == 200
    assert "저장한 공고" in r.text


def test_bookmark_shown_on_job_list(client):
    login(client, "seeker1")
    conn = get_sqlite()
    job_id = conn.execute("SELECT id FROM job_postings LIMIT 1").fetchone()["id"]
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.execute("INSERT INTO bookmarks (user_id, job_id) VALUES (?,?)", (uid, job_id))
    conn.commit()
    conn.close()
    r = client.get("/jobs")
    assert r.status_code == 200
    assert "fas fa-heart" in r.text


def test_bookmark_shown_on_job_detail(client):
    login(client, "seeker1")
    conn = get_sqlite()
    job_id = conn.execute("SELECT id FROM job_postings WHERE status='open' LIMIT 1").fetchone()["id"]
    uid = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
    conn.execute("INSERT INTO bookmarks (user_id, job_id) VALUES (?,?)", (uid, job_id))
    conn.commit()
    conn.close()
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    assert "저장됨" in r.text
