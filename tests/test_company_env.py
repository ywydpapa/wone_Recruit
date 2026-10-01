import json
from urllib.parse import urlencode

from core.db import get_sqlite
from tests.conftest import login


def post_profile(client, fields):
    return client.post(
        "/company/profile",
        content=urlencode(fields, doseq=True),
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def test_save_env_and_esg(client):
    login(client, "comp1")
    fields = [
        ("company_name", "한빛테크"),
        ("remote_ok", "on"),
        ("flexible_ok", "on"),
        ("work_env_note", "주 2회 재택근무"),
        ("esg_items", "장애인 표준사업장"),
        ("esg_items", "ESG 보고서 공개"),
        ("esg_note", "매년 지속가능경영보고서를 공개합니다."),
    ]
    r = post_profile(client, fields)
    assert r.status_code == 303

    conn = get_sqlite()
    company = conn.execute("SELECT * FROM companies WHERE company_name='한빛테크'").fetchone()
    conn.close()
    assert company["remote_ok"] == 1
    assert company["flexible_ok"] == 1
    assert company["shared_office_ok"] == 0
    assert company["work_env_note"] == "주 2회 재택근무"
    assert set(json.loads(company["esg_items"])) == {"장애인 표준사업장", "ESG 보고서 공개"}
    assert company["esg_note"] == "매년 지속가능경영보고서를 공개합니다."


def test_invalid_esg_item_ignored(client):
    login(client, "comp1")
    fields = [
        ("company_name", "한빛테크"),
        ("esg_items", "장애인 표준사업장"),
        ("esg_items", "없는항목입니다"),
    ]
    post_profile(client, fields)

    conn = get_sqlite()
    company = conn.execute("SELECT esg_items FROM companies WHERE company_name='한빛테크'").fetchone()
    conn.close()
    items = json.loads(company["esg_items"])
    assert "장애인 표준사업장" in items
    assert "없는항목입니다" not in items


def test_levy_block_renders_with_correct_numbers(client):
    login(client, "comp1")
    fields = [
        ("company_name", "한빛테크"),
        ("employee_count", "120"),
        ("disabled_count", "2"),
    ]
    post_profile(client, fields)

    r = client.get("/company/profile")
    assert r.status_code == 200
    assert "의무고용 대상 여부" in r.text
    assert "대상 (50인 이상)" in r.text
    assert "대상 (100인 이상)" in r.text
    assert "3명" in r.text
    assert "1명 미달" in r.text


def test_seeker_company_page_shows_env_badges(client):
    login(client, "comp1")
    fields = [
        ("company_name", "한빛테크"),
        ("remote_ok", "on"),
        ("esg_items", "장애인 표준사업장"),
    ]
    post_profile(client, fields)

    conn = get_sqlite()
    company = conn.execute("SELECT id FROM companies WHERE company_name='한빛테크'").fetchone()
    conn.close()

    client2 = client
    login(client2, "seeker1")
    r = client2.get(f"/companies/{company['id']}")
    assert r.status_code == 200
    assert "재택근무 가능" in r.text
    assert "장애인 표준사업장" in r.text


def test_empty_env_and_esg_blocks_hidden(client):
    login(client, "comp3")
    fields = [("company_name", "넥스트미디어")]
    post_profile(client, fields)

    conn = get_sqlite()
    company = conn.execute("SELECT id FROM companies WHERE company_name='넥스트미디어'").fetchone()
    conn.close()

    login(client, "seeker1")
    r = client.get(f"/companies/{company['id']}")
    assert r.status_code == 200
    assert ">근무환경</h6>" not in r.text
    assert ">ESG / 사회공헌</h6>" not in r.text
