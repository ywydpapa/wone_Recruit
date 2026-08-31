from tests.conftest import login


def test_css_has_mobile_media_query(client):
    r = client.get("/static/css/style.css")
    assert r.status_code == 200
    assert "@media (max-width: 767.98px)" in r.text
    assert "dl.row" in r.text  # dl/dd 스택 레이아웃


def test_css_has_small_mobile_query(client):
    r = client.get("/static/css/style.css")
    assert r.status_code == 200
    assert "@media (max-width: 479.98px)" in r.text


def test_dashboard_renders(client):
    login(client, "seeker1")
    r = client.get("/")
    assert r.status_code == 200


def test_jobs_page_renders(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200


def test_job_detail_renders(client):
    login(client, "seeker1")
    from core.db import get_sqlite
    conn = get_sqlite()
    job_id = conn.execute("SELECT id FROM job_postings WHERE status='open' LIMIT 1").fetchone()["id"]
    conn.close()
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200


def test_profile_renders(client):
    login(client, "seeker1")
    r = client.get("/profile")
    assert r.status_code == 200


def test_applications_renders(client):
    login(client, "seeker1")
    r = client.get("/applications")
    assert r.status_code == 200


def test_bookmarks_renders(client):
    login(client, "seeker1")
    r = client.get("/bookmarks")
    assert r.status_code == 200
