from core.pagination import page_info
from tests.conftest import login


def test_page_info_single_page():
    info = page_info(5, 1)
    assert info["total_pages"] == 1
    assert not info["has_prev"]
    assert not info["has_next"]


def test_page_info_multi_page():
    info = page_info(50, 2)
    assert info["total_pages"] == 3
    assert info["has_prev"]
    assert info["has_next"]


def test_page_info_page_range():
    info = page_info(200, 5)
    assert info["page"] == 5
    assert 5 in info["page_range"]


def test_jobs_pagination(client):
    login(client, "seeker1")
    r = client.get("/jobs?page=1", follow_redirects=False)
    assert r.status_code == 200


def test_invalid_page_number(client):
    login(client, "seeker1")
    r = client.get("/jobs?page=-1", follow_redirects=False)
    assert r.status_code == 200


def test_op_seekers_pagination(client):
    login(client, "op1")
    r = client.get("/op/seekers?page=1", follow_redirects=False)
    assert r.status_code == 200
