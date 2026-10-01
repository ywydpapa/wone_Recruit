from tests.conftest import login
from scripts.build_refs import tidy_certs


def test_certs_unauthed(client):
    r = client.get("/api/refs/certs?q=정보", follow_redirects=False)
    assert r.status_code == 303


def test_certs_empty_query(client):
    login(client, "seeker1")
    r = client.get("/api/refs/certs?q=")
    assert r.json() == []


def test_certs_search(client):
    login(client, "seeker1")
    r = client.get("/api/refs/certs?q=정보처리기사")
    data = r.json()
    assert any(c["name"] == "정보처리기사" for c in data)
    hit = next(c for c in data if c["name"] == "정보처리기사")
    assert hit["org"] == "한국산업인력공단"


def test_certs_prefix_priority(client):
    login(client, "seeker1")
    r = client.get("/api/refs/certs?q=워드")
    data = r.json()
    assert len(data) >= 1
    assert data[0]["name"] == "워드프로세서"


def test_certs_limit_10(client):
    login(client, "seeker1")
    r = client.get("/api/refs/certs?q=기사")
    assert len(r.json()) <= 10


def test_schools_unauthed(client):
    r = client.get("/api/refs/schools?q=서울", follow_redirects=False)
    assert r.status_code == 303


def test_schools_search(client):
    login(client, "seeker1")
    r = client.get("/api/refs/schools?q=서울대학교")
    data = r.json()
    hit = next((s for s in data if s["name"] == "서울대학교"), None)
    assert hit is not None
    assert hit["level"] == "대학교(4년)"


def test_schools_empty_query(client):
    login(client, "seeker1")
    r = client.get("/api/refs/schools?q=")
    assert r.json() == []


def test_tidy_certs_normalizes_grade_paren():
    certs = [{"name": "사회복지사(1급)", "org": ""}, {"name": "사회복지사 1급", "org": "한국산업인력공단"}]
    result = tidy_certs(certs)
    assert len(result) == 1
    assert result[0] == {"name": "사회복지사 1급", "org": "한국산업인력공단"}


def test_tidy_certs_drops_bare():
    certs = [
        {"name": "컴퓨터활용능력", "org": ""},
        {"name": "컴퓨터활용능력(1급)", "org": ""},
        {"name": "컴퓨터활용능력(2급)", "org": ""},
    ]
    names = [c["name"] for c in tidy_certs(certs)]
    assert names == ["컴퓨터활용능력 1급", "컴퓨터활용능력 2급"]


def test_tidy_certs_keeps_manual_bare_exception():
    certs = [
        {"name": "정신보건사회복지사", "org": ""},
        {"name": "정신보건사회복지사(1급)", "org": ""},
    ]
    names = [c["name"] for c in tidy_certs(certs)]
    assert names == ["정신보건사회복지사 (구)", "정신보건사회복지사 1급 (구)"]
