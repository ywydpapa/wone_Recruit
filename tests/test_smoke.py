from tests.conftest import login


def test_login_page_renders(client):
    r = client.get("/login")
    assert r.status_code == 200


def test_login_redirects_to_dashboard(client):
    r = login(client, "op1")
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_api_regions_sido_list(client):
    r = client.get("/api/regions")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 16
    assert "서울특별시" in data
    assert "부산광역시" in data


def test_api_regions_sigungu(client):
    r = client.get("/api/regions?sido=부산광역시")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 16
    names = [d["sigungu"] for d in data]
    assert "해운대구" in names
