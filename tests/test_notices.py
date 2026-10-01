from tests.conftest import login
from core.db import get_sqlite


def _create(client, title="테스트 공지", content="테스트 내용입니다.", audience="all", pinned=False):
    data = {"title": title, "content": content, "audience": audience}
    if pinned:
        data["pinned"] = "on"
    return client.post("/op/notices", data=data, follow_redirects=False)


def test_op_notice_create(client):
    login(client, "op1")
    r = _create(client, title="신규 공지 테스트")
    assert r.status_code == 303
    r = client.get("/op/notices")
    assert "신규 공지 테스트" in r.text


def test_op_notice_edit(client):
    login(client, "op1")
    _create(client, title="수정 전 제목")
    conn = get_sqlite()
    row = conn.execute("SELECT id FROM notices WHERE title='수정 전 제목'").fetchone()
    conn.close()
    r = client.post(
        f"/op/notices/{row['id']}",
        data={"title": "수정 후 제목", "content": "수정된 내용", "audience": "seeker"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    r = client.get("/op/notices")
    assert "수정 후 제목" in r.text
    assert "수정 전 제목" not in r.text


def test_op_notice_delete(client):
    login(client, "op1")
    _create(client, title="삭제될 공지")
    conn = get_sqlite()
    row = conn.execute("SELECT id FROM notices WHERE title='삭제될 공지'").fetchone()
    conn.close()
    r = client.post(f"/op/notices/{row['id']}/delete", follow_redirects=False)
    assert r.status_code == 303
    r = client.get("/op/notices")
    assert "삭제될 공지" not in r.text


def test_non_operator_cannot_access_op_notices(client):
    login(client, "seeker1")
    r = client.get("/op/notices", follow_redirects=False)
    assert r.status_code in (303, 403)
    r = client.get("/op/notices/new", follow_redirects=False)
    assert r.status_code in (303, 403)
    r = client.post("/op/notices", data={"title": "t", "content": "c", "audience": "all"}, follow_redirects=False)
    assert r.status_code in (303, 403)


def test_audience_filtering(client):
    login(client, "op1")
    _create(client, title="기업 전용 공지", audience="company")
    _create(client, title="구직자 전용 공지", audience="seeker")

    login(client, "seeker1")
    r = client.get("/notices")
    assert "구직자 전용 공지" in r.text
    assert "기업 전용 공지" not in r.text

    login(client, "comp1")
    r = client.get("/notices")
    assert "기업 전용 공지" in r.text
    assert "구직자 전용 공지" not in r.text

    login(client, "counsel1")
    r = client.get("/notices")
    assert "기업 전용 공지" not in r.text
    assert "구직자 전용 공지" not in r.text


def test_pinned_ordering(client):
    login(client, "op1")
    _create(client, title="일반 공지")
    _create(client, title="고정 공지", pinned=True)
    r = client.get("/notices")
    assert r.text.index("고정 공지") < r.text.index("일반 공지")


def test_notice_views_increment(client):
    login(client, "op1")
    _create(client, title="조회수 테스트 공지")
    conn = get_sqlite()
    row = conn.execute("SELECT id, views FROM notices WHERE title='조회수 테스트 공지'").fetchone()
    conn.close()
    assert row["views"] == 0

    client.get(f"/notices/{row['id']}")
    client.get(f"/notices/{row['id']}")
    conn = get_sqlite()
    row2 = conn.execute("SELECT views FROM notices WHERE id=?", (row["id"],)).fetchone()
    conn.close()
    assert row2["views"] == 2


def test_notice_detail_denies_wrong_audience(client):
    login(client, "op1")
    _create(client, title="기업 전용 상세 공지", audience="company")
    conn = get_sqlite()
    row = conn.execute("SELECT id FROM notices WHERE title='기업 전용 상세 공지'").fetchone()
    conn.close()

    login(client, "seeker1")
    r = client.get(f"/notices/{row['id']}", follow_redirects=False)
    assert r.status_code == 303


def test_op_notice_validation_empty_title(client):
    login(client, "op1")
    r = client.post(
        "/op/notices", data={"title": "  ", "content": "내용", "audience": "all"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "error=title_required" in r.headers["location"]
    conn = get_sqlite()
    cnt = conn.execute("SELECT COUNT(*) FROM notices WHERE content='내용'").fetchone()[0]
    conn.close()
    assert cnt == 0


def test_op_notice_validation_bad_audience(client):
    login(client, "op1")
    r = client.post(
        "/op/notices", data={"title": "제목", "content": "내용", "audience": "everyone"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "error=bad_audience" in r.headers["location"]
