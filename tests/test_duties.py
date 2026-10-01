import json
import re

from core.db import get_sqlite
from tests.conftest import login


def get_category(conn, onsite=0):
    return conn.execute("SELECT * FROM job_categories WHERE onsite_required=? LIMIT 1", (onsite,)).fetchone()


def test_duty_list_company(client):
    login(client, "comp1")
    r = client.get("/company/duties")
    assert r.status_code == 200
    assert "직무 관리" in r.text
    assert "원격근무 추천 직무" in r.text


def test_duty_new_form_prefill_from_category(client):
    login(client, "comp1")
    conn = get_sqlite()
    cat = get_category(conn)
    conn.close()
    r = client.get(f"/company/duties/new?category_id={cat['id']}")
    assert r.status_code == 200
    assert f'value="{cat["minor_name_ko"]}"' in r.text
    # 적합도(fit) 값이 카테고리 기본값으로 복사되어 체크되어 있어야 함
    checked_id = f'id="fit_physical_lower_{cat["fit_physical_lower"]}"'
    assert re.search(re.escape(checked_id) + r'\s+value="\d"\s+checked', r.text)


def test_duty_create_and_edit_own(client):
    login(client, "comp1")
    r = client.post("/company/duties", data={
        "title": "데이터 라벨링 직무",
        "category_id": "",
        "tasks": "이미지 라벨링",
        "tools": "Label Studio",
        "difficulty": "mid",
        "remote_ok": "1",
        "note": "테스트 직무",
        "fit_physical_lower": "3",
        "fit_physical_upper": "2",
        "fit_hearing": "3",
        "fit_visual_low": "1",
        "fit_intellectual": "1",
        "fit_autism": "2",
        "fit_mental": "2",
        "fit_internal_organ": "3",
        "fit_brain_lesion": "2",
    }, follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    duty = conn.execute("SELECT * FROM company_duties WHERE title='데이터 라벨링 직무'").fetchone()
    conn.close()
    assert duty is not None
    assert duty["remote_ok"] == 1
    fit = json.loads(duty["fit"])
    assert fit["fit_physical_lower"] == 3

    r = client.get(f"/company/duties/{duty['id']}/edit")
    assert r.status_code == 200
    assert "데이터 라벨링 직무" in r.text

    r = client.post(f"/company/duties/{duty['id']}", data={
        "title": "데이터 라벨링 직무 수정",
        "category_id": "",
        "tasks": "이미지 라벨링 수정",
        "tools": "Label Studio",
        "difficulty": "high",
        "remote_ok": "0",
        "note": "",
        "fit_physical_lower": "3",
        "fit_physical_upper": "2",
        "fit_hearing": "3",
        "fit_visual_low": "1",
        "fit_intellectual": "1",
        "fit_autism": "2",
        "fit_mental": "2",
        "fit_internal_organ": "3",
        "fit_brain_lesion": "2",
    }, follow_redirects=False)
    assert r.status_code == 303
    conn = get_sqlite()
    duty2 = conn.execute("SELECT * FROM company_duties WHERE id=?", (duty["id"],)).fetchone()
    conn.close()
    assert duty2["title"] == "데이터 라벨링 직무 수정"
    assert duty2["difficulty"] == "high"
    assert duty2["remote_ok"] == 0


def test_duty_fit_clamp(client):
    login(client, "comp1")
    r = client.post("/company/duties", data={
        "title": "적합성 검증 테스트",
        "difficulty": "mid",
        "remote_ok": "1",
        "fit_physical_lower": "9",
        "fit_physical_upper": "abc",
        "fit_hearing": "-1",
        "fit_visual_low": "2",
    }, follow_redirects=False)
    assert r.status_code == 303
    conn = get_sqlite()
    duty = conn.execute("SELECT * FROM company_duties WHERE title='적합성 검증 테스트'").fetchone()
    conn.close()
    fit = json.loads(duty["fit"])
    assert fit["fit_physical_lower"] == 0
    assert fit["fit_physical_upper"] == 0
    assert fit["fit_hearing"] == 0
    assert fit["fit_visual_low"] == 2


def test_duty_other_company_blocked(client):
    login(client, "comp1")
    r = client.post("/company/duties", data={
        "title": "타사 접근 테스트 직무",
        "difficulty": "mid",
        "remote_ok": "1",
    }, follow_redirects=False)
    assert r.status_code == 303
    conn = get_sqlite()
    duty = conn.execute("SELECT * FROM company_duties WHERE title='타사 접근 테스트 직무'").fetchone()
    conn.close()

    login(client, "comp2")
    r = client.get(f"/company/duties/{duty['id']}/edit")
    assert r.status_code == 404
    r = client.post(f"/company/duties/{duty['id']}", data={"title": "해킹시도", "difficulty": "mid", "remote_ok": "1"})
    assert r.status_code == 404
    r = client.post(f"/company/duties/{duty['id']}/delete")
    assert r.status_code == 404


def test_duty_analysis_request_notifies_operator(client):
    login(client, "comp1")
    r = client.post("/company/duties", data={
        "title": "분석 요청 대상 직무",
        "difficulty": "mid",
        "remote_ok": "1",
    }, follow_redirects=False)
    conn = get_sqlite()
    duty = conn.execute("SELECT * FROM company_duties WHERE title='분석 요청 대상 직무'").fetchone()
    op1 = conn.execute("SELECT id FROM users WHERE username='op1'").fetchone()
    conn.close()

    r = client.post(f"/company/duties/{duty['id']}/analysis", data={
        "request_text": "이 직무가 지체장애인에게 적합한지 분석 부탁드립니다.",
    }, follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    duty2 = conn.execute("SELECT * FROM company_duties WHERE id=?", (duty["id"],)).fetchone()
    notif = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND link=?", (op1["id"], f"/op/duties/{duty['id']}")
    ).fetchone()
    conn.close()
    assert duty2["analysis_status"] == "requested"
    assert notif is not None


def test_operator_answers_then_company_notified(client):
    login(client, "comp1")
    client.post("/company/duties", data={
        "title": "운영자 답변 테스트 직무",
        "difficulty": "mid",
        "remote_ok": "1",
    }, follow_redirects=False)
    conn = get_sqlite()
    duty = conn.execute("SELECT * FROM company_duties WHERE title='운영자 답변 테스트 직무'").fetchone()
    comp_user = conn.execute("SELECT user_id FROM companies c JOIN users u ON c.user_id=u.id WHERE u.username='comp1'").fetchone()
    conn.close()
    client.post(f"/company/duties/{duty['id']}/analysis", data={"request_text": "분석 요청"}, follow_redirects=False)

    login(client, "op1")
    r = client.get("/op/duties")
    assert r.status_code == 200
    r = client.get(f"/op/duties/{duty['id']}")
    assert r.status_code == 200

    r = client.post(f"/op/duties/{duty['id']}/analysis", data={
        "analysis_note": "지체장애인에게 적합한 직무로 판단됩니다.",
        "fit_physical_lower": "3",
        "fit_physical_upper": "3",
        "fit_hearing": "2",
        "fit_visual_low": "1",
        "fit_intellectual": "1",
        "fit_autism": "2",
        "fit_mental": "2",
        "fit_internal_organ": "3",
        "fit_brain_lesion": "2",
    }, follow_redirects=False)
    assert r.status_code == 303

    conn = get_sqlite()
    duty2 = conn.execute("SELECT * FROM company_duties WHERE id=?", (duty["id"],)).fetchone()
    op1 = conn.execute("SELECT id FROM users WHERE username='op1'").fetchone()
    notif = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND link=?",
        (comp_user["user_id"], f"/company/duties/{duty['id']}/edit"),
    ).fetchone()
    conn.close()
    assert duty2["analysis_status"] == "done"
    assert duty2["analyzed_by"] == op1["id"]
    assert duty2["analyzed_at"] is not None
    assert notif is not None


def test_non_operator_blocked_from_op_duties(client):
    login(client, "comp1")
    r = client.get("/op/duties")
    assert r.status_code == 403

    login(client, "seeker1")
    r = client.get("/op/duties")
    assert r.status_code == 403


def test_job_form_prefill_via_duty_id(client):
    login(client, "comp1")
    client.post("/company/duties", data={
        "title": "공고 연동 테스트 직무",
        "tasks": "공고 연동 업무 내용",
        "tools": "Excel, Slack",
        "difficulty": "mid",
        "remote_ok": "1",
    }, follow_redirects=False)
    conn = get_sqlite()
    duty = conn.execute("SELECT * FROM company_duties WHERE title='공고 연동 테스트 직무'").fetchone()
    conn.close()

    r = client.get(f"/company/duties/{duty['id']}/job", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"/company/jobs/new?duty_id={duty['id']}"

    r = client.get(f"/company/jobs/new?duty_id={duty['id']}")
    assert r.status_code == 200
    assert 'value="공고 연동 테스트 직무"' in r.text
    assert "공고 연동 업무 내용" in r.text
    assert "Excel, Slack" in r.text
