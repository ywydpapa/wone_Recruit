import io
from tests.conftest import login


def test_profile_with_resume_upload(client):
    login(client, "seeker1")
    pdf_content = b"%PDF-1.4 fake pdf content for testing"
    r = client.post("/profile", data={
        "disability_type_id": "1",
        "severity": "경증",
        "gender": "여",
        "consent_sensitive": "1",
    }, files={"resume": ("resume.pdf", io.BytesIO(pdf_content), "application/pdf")},
    follow_redirects=False)
    assert r.status_code == 303

    r = client.get("/profile")
    assert r.status_code == 200
    assert "이력서 보기" in r.text


def test_profile_reject_non_pdf_resume(client):
    login(client, "seeker1")
    r = client.post("/profile", data={
        "disability_type_id": "1",
        "severity": "경증",
        "gender": "여",
        "consent_sensitive": "1",
    }, files={"resume": ("image.jpg", io.BytesIO(b"fake image"), "image/jpeg")},
    follow_redirects=False)
    assert r.status_code == 303
    # PDF 아닌 파일은 저장 안됨
    r = client.get("/profile")
    assert "이력서 보기" not in r.text


def test_company_logo_upload(client):
    login(client, "comp1")
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    r = client.post("/company/profile", data={
        "company_name": "한빛테크",
    }, files={"logo": ("logo.png", io.BytesIO(png_header), "image/png")},
    follow_redirects=False)
    assert r.status_code == 303

    r = client.get("/company/profile")
    assert r.status_code == 200
