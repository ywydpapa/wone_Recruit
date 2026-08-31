from tests.conftest import login


def test_company_profile_requires_login(client):
    r = client.get("/company/profile", follow_redirects=False)
    assert r.status_code in (303, 403)


def test_company_profile_form_renders(client):
    login(client, "comp1")
    r = client.get("/company/profile")
    assert r.status_code == 200
    assert "기업 정보" in r.text or "기업" in r.text


def test_company_profile_save(client):
    login(client, "comp1")
    r = client.post("/company/profile", data={
        "company_name": "한빛테크",
        "biz_no": "123-45-67890",
        "industry": "IT서비스",
        "employee_count": 250,
        "disabled_count": 3,
        "region_id": 1,
        "intro": "테스트 기업",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "success" in r.headers["location"]


def test_company_profile_v2_save(client):
    login(client, "comp1")
    from urllib.parse import urlencode
    fields = [
        ("company_name", "한빛테크"),
        ("biz_no", "123-45-67890"),
        ("industry", "IT/소프트웨어"),
        ("employee_count", "250"),
        ("disabled_count", "3"),
        ("region_id", "1"),
        ("intro", "테스트 기업"),
        ("website", "https://hanbit.example.com"),
        ("company_size", "중소기업(50~299인)"),
        ("accessibility_facilities", "휠체어접근"),
        ("accessibility_facilities", "엘리베이터"),
        ("accessibility_note", "1층 무장애 동선"),
        ("hiring_experience", "1"),
        ("retention_note", "장애인 3명 재직"),
        ("benefits", "4대보험, 유연근무제"),
    ]
    r = client.post(
        "/company/profile",
        content=urlencode(fields, doseq=True),
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "success" in r.headers["location"]


def test_company_accessibility_stored(client):
    login(client, "comp1")
    from urllib.parse import urlencode
    fields = [
        ("company_name", "한빛테크"),
        ("accessibility_facilities", "휠체어접근"),
        ("accessibility_facilities", "장애인화장실"),
        ("accessibility_facilities", "엘리베이터"),
    ]
    client.post(
        "/company/profile",
        content=urlencode(fields, doseq=True),
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    r = client.get("/company/profile")
    assert r.status_code == 200
    assert "휠체어접근" in r.text
    assert "장애인화장실" in r.text
    assert "엘리베이터" in r.text
