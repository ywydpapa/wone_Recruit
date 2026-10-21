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
    # PDF가 아닌 파일은 저장되지 않음
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


def _upload_resume(client):
    login(client, "seeker1")
    client.post("/profile", data={
        "disability_type_id": "1",
        "severity": "경증",
        "gender": "여",
        "consent_sensitive": "1",
    }, files={"resume": ("resume.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
    follow_redirects=False)
    from core.db import get_sqlite
    conn = get_sqlite()
    row = conn.execute(
        "SELECT sp.resume_path, u.username FROM seeker_profiles sp, users u "
        "JOIN companies co ON co.user_id=u.id "
        "JOIN job_postings j ON j.company_id=co.id "
        "JOIN candidacies c ON c.job_id=j.id "
        "WHERE sp.user_id=c.seeker_user_id "
        "AND c.seeker_user_id=(SELECT id FROM users WHERE username='seeker1')"
    ).fetchone()
    conn.close()
    return row["resume_path"], row["username"]


def test_resume_not_public(client):
    path, _ = _upload_resume(client)
    assert path.startswith("/files/profile_resumes/")
    name = path.rsplit("/", 1)[-1]
    assert client.get(f"/static/uploads/profile_resumes/{name}").status_code == 404

    client.get("/logout")
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


def test_resume_access_by_role(client):
    path, comp = _upload_resume(client)
    assert client.get(path).status_code == 200

    login(client, comp)
    assert client.get(path).status_code == 200

    other = "comp2" if comp != "comp2" else "comp3"
    login(client, other)
    assert client.get(path).status_code == 404

    login(client, "counsel1")
    assert client.get(path).status_code == 404

    login(client, "op1")
    assert client.get(path).status_code == 200


def test_files_path_traversal(client):
    login(client, "op1")
    assert client.get("/files/profile_resumes/..%2F..%2Fmain.py").status_code == 404
    assert client.get("/files/logos/x.png").status_code == 404
