from core.db import get_sqlite
from tests.conftest import login


def _get_unapplied_job_id():
    conn = get_sqlite()
    row = conn.execute(
        """SELECT jp.id FROM job_postings jp
           WHERE jp.status='open'
             AND jp.id NOT IN (
                 SELECT job_id FROM candidacies
                 WHERE seeker_user_id=(SELECT id FROM users WHERE username='seeker1')
             )
           LIMIT 1"""
    ).fetchone()
    conn.close()
    return row["id"]


def test_apply_form_shows_profile_summary(client):
    login(client, "seeker1")
    job_id = _get_unapplied_job_id()
    r = client.get(f"/apply/{job_id}")
    assert r.status_code == 200
    assert "내 프로필 요약" in r.text
    assert "김하늘" in r.text  # seeker1 이름


def test_apply_form_shows_job_info(client):
    login(client, "seeker1")
    conn = get_sqlite()
    job = conn.execute(
        """SELECT jp.id, jp.title FROM job_postings jp
           WHERE jp.status='open'
             AND jp.id NOT IN (
                 SELECT job_id FROM candidacies
                 WHERE seeker_user_id=(SELECT id FROM users WHERE username='seeker1')
             )
           LIMIT 1"""
    ).fetchone()
    conn.close()
    r = client.get(f"/apply/{job['id']}")
    assert r.status_code == 200
    assert "지원 공고" in r.text
    assert job["title"] in r.text


def test_apply_form_shows_company_name(client):
    login(client, "seeker1")
    job_id = _get_unapplied_job_id()
    r = client.get(f"/apply/{job_id}")
    assert r.status_code == 200
    assert "한빛테크" in r.text


def test_apply_form_shows_disability_type(client):
    login(client, "seeker1")
    job_id = _get_unapplied_job_id()
    r = client.get(f"/apply/{job_id}")
    assert r.status_code == 200
    assert "시각" in r.text  # seeker1 장애유형


def test_apply_form_has_confirm_modal(client):
    login(client, "seeker1")
    job_id = _get_unapplied_job_id()
    r = client.get(f"/apply/{job_id}")
    assert r.status_code == 200
    assert "confirmModal" in r.text
    assert "정말 지원하시겠습니까" in r.text


def test_apply_submit_still_works(client):
    login(client, "seeker1")
    conn = get_sqlite()
    job_id = conn.execute(
        """SELECT jp.id FROM job_postings jp
           WHERE jp.status='open'
             AND jp.id NOT IN (SELECT job_id FROM candidacies WHERE seeker_user_id=(SELECT id FROM users WHERE username='seeker1'))
           LIMIT 1"""
    ).fetchone()["id"]
    conn.close()
    r = client.post(f"/apply/{job_id}", data={"cover_letter": "테스트 지원서"}, follow_redirects=False)
    assert r.status_code == 303
    assert "applications" in r.headers["location"]
