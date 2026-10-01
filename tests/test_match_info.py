import json

from tests.conftest import login
from core.db import get_sqlite
from core.security import hash_password


def make_seeker(username, name="새구직자"):
    conn = get_sqlite()
    cur = conn.execute(
        "INSERT INTO users (username, password, name, phone, role) VALUES (?,?,?,?,'seeker')",
        (username, hash_password("admin1234"), name, "010-0000-0000"),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def uid(username):
    conn = get_sqlite()
    row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return row["id"]


def assign(manager_id, seeker_id, by_id):
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO manager_assignments (manager_user_id, seeker_user_id, assigned_by) VALUES (?,?,?)",
        (manager_id, seeker_id, by_id),
    )
    conn.commit()
    conn.close()


def cat_id(name):
    conn = get_sqlite()
    row = conn.execute("SELECT id FROM job_categories WHERE minor_name_ko=?", (name,)).fetchone()
    conn.close()
    return row["id"]


def test_assigned_manager_can_view_form(client):
    seeker1 = uid("seeker1")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker1, op_id)

    login(client, "counsel1")
    r = client.get(f"/mgr/seekers/{seeker1}/match-info")
    assert r.status_code == 200
    assert "필요 직무" in r.text
    assert "보조장비" in r.text
    assert "지원 필요사항" in r.text
    assert "화면낭독기" in r.text


def test_save_drops_invalid_ids_and_names(client):
    seeker1 = uid("seeker1")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker1, op_id)
    valid_cat = cat_id("데이터 입력")

    login(client, "counsel1")
    r = client.post(
        f"/mgr/seekers/{seeker1}/match-info",
        data={
            "target_categories": [str(valid_cat), "999999"],
            "assistive_tech": ["화면확대기", "없는장비"],
            "accommodation_needs": ["재택근무", "없는지원"],
            "match_note": "스크린리더 사용에 능숙함",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "matched=1" in r.headers["location"]

    conn = get_sqlite()
    profile = conn.execute("SELECT * FROM seeker_profiles WHERE user_id=?", (seeker1,)).fetchone()
    conn.close()
    assert json.loads(profile["target_categories"]) == [valid_cat]
    assert json.loads(profile["assistive_tech"]) == ["화면확대기"]
    assert json.loads(profile["accommodation_needs"]) == ["재택근무"]
    assert profile["match_note"] == "스크린리더 사용에 능숙함"
    assert profile["match_updated_at"] is not None
    assert profile["match_updated_by"] == manager_id


def test_unassigned_manager_gets_404(client):
    seeker1 = uid("seeker1")

    login(client, "counsel1")
    r = client.get(f"/mgr/seekers/{seeker1}/match-info")
    assert r.status_code == 404

    r = client.post(
        f"/mgr/seekers/{seeker1}/match-info",
        data={"match_note": "권한 없는 접근"},
        follow_redirects=False,
    )
    assert r.status_code == 404


def test_seeker_detail_shows_match_info_card(client):
    seeker_id = make_seeker("seeker9")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker_id, op_id)

    login(client, "counsel1")
    r = client.get(f"/mgr/seekers/{seeker_id}")
    assert r.status_code == 200
    assert "매칭 정보" in r.text
    assert "아직 매칭 정보가 입력되지 않았습니다" in r.text

    valid_cat = cat_id("이미지 데이터 라벨링")
    client.post(
        f"/mgr/seekers/{seeker_id}/match-info",
        data={
            "target_categories": [str(valid_cat)],
            "assistive_tech": ["화면확대기"],
            "accommodation_needs": ["점자자료"],
            "match_note": "상담 중 파악한 참고사항",
        },
        follow_redirects=False,
    )

    r = client.get(f"/mgr/seekers/{seeker_id}")
    assert r.status_code == 200
    assert "이미지 데이터 라벨링" in r.text
    assert "화면확대기" in r.text
    assert "점자자료" in r.text
    assert "상담 중 파악한 참고사항" in r.text
    assert "이상담" in r.text


def test_next_outside_mgr_is_ignored(client):
    seeker1 = uid("seeker1")
    manager_id = uid("counsel1")
    op_id = uid("op1")
    assign(manager_id, seeker1, op_id)

    login(client, "counsel1")
    r = client.post(
        f"/mgr/seekers/{seeker1}/match-info",
        data={"next": "https://evil.example.com", "match_note": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/mgr/seekers/{seeker1}?matched=1"
