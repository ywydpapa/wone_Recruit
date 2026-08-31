from tests.conftest import login


def test_seeker_jobs_renders_cards(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    assert b"item-card" in r.content


def test_op_jobs_renders_table(client):
    login(client, "op1")
    r = client.get("/op/jobs")
    assert r.status_code == 200
    assert b"table" in r.content


def test_op_seeker_detail_renders_profile_cards(client):
    login(client, "op1")
    from core.db import get_sqlite
    conn = get_sqlite()
    seeker = conn.execute("SELECT id FROM users WHERE role='seeker' LIMIT 1").fetchone()
    conn.close()
    r = client.get(f"/op/seekers/{seeker['id']}")
    assert r.status_code == 200
    assert b"profile-card" in r.content
    assert b"table-bordered" not in r.content


def test_seeker_jobs_card_has_accommodation_tags(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    text = r.text
    assert '["' not in text


def test_seeker_jobs_wcag_article_headings(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    # article이 있으면 h3 필수
    text = r.text
    article_count = text.count("<article")
    h3_count = text.count("<h3")
    if article_count > 0:
        assert h3_count >= article_count
