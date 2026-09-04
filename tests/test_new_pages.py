from tests.conftest import login


def test_applicants_all_requires_login(client):
    r = client.get("/company/applicants", follow_redirects=False)
    assert r.status_code in (303, 403)


def test_applicants_all_renders(client):
    login(client, "comp1")
    r = client.get("/company/applicants")
    assert r.status_code == 200
    assert "지원자 관리" in r.text


def test_applicants_all_filter_status(client):
    login(client, "comp1")
    r = client.get("/company/applicants?status=pending")
    assert r.status_code == 200


def test_calendar_requires_login(client):
    r = client.get("/company/calendar", follow_redirects=False)
    assert r.status_code in (303, 403)


def test_calendar_renders(client):
    login(client, "comp1")
    r = client.get("/company/calendar")
    assert r.status_code == 200
    assert "면접 캘린더" in r.text


def test_calendar_with_month(client):
    login(client, "comp1")
    r = client.get("/company/calendar?year=2026&month=3")
    assert r.status_code == 200
    assert "2026" in r.text


def test_recommendations_requires_login(client):
    r = client.get("/company/recommendations", follow_redirects=False)
    assert r.status_code in (303, 403)


def test_recommendations_renders(client):
    login(client, "comp1")
    r = client.get("/company/recommendations")
    assert r.status_code == 200
    assert "추천 인재" in r.text
