from core.db import get_sqlite
from tests.conftest import login


def test_company_detail_page(client):
    login(client, "seeker1")
    conn = get_sqlite()
    company = conn.execute("SELECT id FROM companies LIMIT 1").fetchone()
    conn.close()
    r = client.get(f"/companies/{company['id']}")
    assert r.status_code == 200
    assert "한빛테크" in r.text


def test_company_detail_shows_facilities(client):
    login(client, "seeker1")
    conn = get_sqlite()
    company = conn.execute("SELECT id FROM companies LIMIT 1").fetchone()
    conn.close()
    r = client.get(f"/companies/{company['id']}")
    assert r.status_code == 200
    assert "접근성 시설" in r.text


def test_company_detail_shows_open_jobs(client):
    login(client, "seeker1")
    conn = get_sqlite()
    company = conn.execute("SELECT id FROM companies LIMIT 1").fetchone()
    conn.close()
    r = client.get(f"/companies/{company['id']}")
    assert r.status_code == 200
    assert "채용 중인 공고" in r.text


def test_company_detail_requires_login(client):
    r = client.get("/companies/1", follow_redirects=False)
    assert r.status_code in (303, 403)


def test_company_detail_not_found(client):
    login(client, "seeker1")
    r = client.get("/companies/9999")
    assert r.status_code == 404


def test_company_link_on_job_detail(client):
    login(client, "seeker1")
    conn = get_sqlite()
    job = conn.execute("SELECT id FROM job_postings WHERE status='open' LIMIT 1").fetchone()
    conn.close()
    r = client.get(f"/jobs/{job['id']}")
    assert r.status_code == 200
    assert "/companies/" in r.text
