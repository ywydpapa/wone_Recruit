from datetime import date

from tests.conftest import login
from core.db import get_sqlite


def _create_notice(client, title, audience="all"):
    return client.post(
        "/op/notices",
        data={"title": title, "content": "내용입니다.", "audience": audience},
        follow_redirects=False,
    )


def test_seeker_home_shows_notices_by_audience(client):
    login(client, "op1")
    _create_notice(client, "전체 공지 테스트", audience="all")
    _create_notice(client, "구직자 공지 테스트", audience="seeker")
    _create_notice(client, "기업 공지 테스트", audience="company")

    login(client, "seeker1")
    r = client.get("/")
    assert "전체 공지 테스트" in r.text
    assert "구직자 공지 테스트" in r.text
    assert "기업 공지 테스트" not in r.text


def test_company_home_unhandled_requests(client):
    login(client, "comp1")
    conn = get_sqlite()
    comp_uid = conn.execute("SELECT id FROM users WHERE username='comp1'").fetchone()["id"]
    cid = conn.execute("SELECT id FROM companies WHERE user_id=?", (comp_uid,)).fetchone()["id"]
    candidacy = conn.execute(
        """SELECT c.id FROM candidacies c JOIN job_postings jp ON c.job_id=jp.id
           WHERE jp.company_id=? LIMIT 1""",
        (cid,),
    ).fetchone()
    assert candidacy is not None

    today = date.today().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT INTO interview_schedules (candidacy_id, interview_date) VALUES (?,?)",
        (candidacy["id"], today),
    )
    conn.execute(
        "INSERT INTO company_duties (company_id, title, analysis_status, analyzed_at) "
        "VALUES (?,'테스트 직무','done', datetime('now','localtime'))",
        (cid,),
    )
    conn.execute(
        "INSERT INTO inquiries (user_id, subject, content, status, answered_at) "
        "VALUES (?,'문의 제목','문의 내용','answered', datetime('now','localtime'))",
        (comp_uid,),
    )
    conn.commit()
    conn.close()

    r = client.get("/")
    assert "미처리 요청" in r.text
    assert "검토 대기 지원자" in r.text
    assert "오늘 면접" in r.text
    assert "직무 분석 완료" in r.text
    assert "답변 완료 문의" in r.text
    assert "처리할 요청이 없습니다" not in r.text


def test_manager_home_shows_notices(client):
    login(client, "op1")
    _create_notice(client, "매니저용 전체 공지", audience="all")
    _create_notice(client, "구직자 전용 공지2", audience="seeker")

    login(client, "counsel1")
    r = client.get("/mgr/")
    assert "매니저용 전체 공지" in r.text
    assert "구직자 전용 공지2" not in r.text
