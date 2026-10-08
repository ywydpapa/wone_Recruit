import re

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


def test_seeker_jobs_card_has_accommodation_tags(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    text = re.sub(r"<script.*?</script>", "", r.text, flags=re.S)
    assert '["' not in text


def test_seeker_jobs_wcag_article_headings(client):
    login(client, "seeker1")
    r = client.get("/jobs")
    assert r.status_code == 200
    # article이 있으면 h3가 반드시 있어야 함
    text = r.text
    article_count = text.count("<article")
    h3_count = text.count("<h3")
    if article_count > 0:
        assert h3_count >= article_count
