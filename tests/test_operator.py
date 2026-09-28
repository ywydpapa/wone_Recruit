from tests.conftest import login
from core.db import get_sqlite


def test_op_seekers_list(client):
    login(client, "op1")
    r = client.get("/op/seekers")
    assert r.status_code == 200


def test_op_seekers_masked_name(client):
    login(client, "op1")
    r = client.get("/op/seekers")
    assert r.status_code == 200
    conn = get_sqlite()
    seeker = conn.execute("SELECT name FROM users WHERE role='seeker' LIMIT 1").fetchone()
    conn.close()
    if seeker and len(seeker["name"]) >= 2:
        assert seeker["name"] not in r.text


def test_op_companies_list(client):
    login(client, "op1")
    r = client.get("/op/companies")
    assert r.status_code == 200


def test_op_jobs_list(client):
    login(client, "op1")
    r = client.get("/op/jobs")
    assert r.status_code == 200


def test_op_requires_operator_role(client):
    login(client, "seeker1")
    r = client.get("/op/seekers", follow_redirects=False)
    assert r.status_code in (303, 403)
