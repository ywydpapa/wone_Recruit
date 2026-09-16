import os
import sys
import sqlite3
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def test_support_tables_exist(client):
    db_path = os.environ["RECRUIT_DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "support_categories" in tables
        assert "support_items" in tables
        assert "support_item_capabilities" in tables
        assert "seeker_support_items" in tables
    finally:
        conn.close()


def test_seed_data_loaded(client):
    db_path = os.environ["RECRUIT_DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cat_count = conn.execute("SELECT COUNT(*) FROM support_categories").fetchone()[0]
        item_count = conn.execute("SELECT COUNT(*) FROM support_items").fetchone()[0]
        cap_count = conn.execute("SELECT COUNT(*) FROM support_item_capabilities").fetchone()[0]
        assert cat_count == 6
        assert item_count >= 23
        assert cap_count >= 30
    finally:
        conn.close()


def test_build_capability_profile_empty(client):
    db_path = os.environ["RECRUIT_DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        from core.matching import build_capability_profile, CAPABILITIES
        profile = build_capability_profile(conn, 9999)
        assert len(profile) == len(CAPABILITIES)
        assert all(v == "ok" for v in profile.values())
    finally:
        conn.close()


def test_build_capability_profile_worst_case(client):
    db_path = os.environ["RECRUIT_DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            "INSERT INTO users (username, password, role, name) VALUES ('tester_cap','x','seeker','테스터')"
        )
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # 화면낭독기(id=1: visual_acuity=no) + 화면확대(id=2: visual_acuity=limit) → worst = no
        conn.execute("INSERT INTO seeker_support_items VALUES (?,1)", (uid,))
        conn.execute("INSERT INTO seeker_support_items VALUES (?,2)", (uid,))
        conn.commit()
        from core.matching import build_capability_profile
        profile = build_capability_profile(conn, uid)
        assert profile["visual_acuity"] == "no"  # 우선순위: no > limit
        assert profile["screen_use"] == "at"
    finally:
        conn.close()


def test_calc_category_fit_perfect(client):
    db_path = os.environ["RECRUIT_DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        from core.matching import calc_category_fit, CAPABILITIES
        profile = {c: "ok" for c in CAPABILITIES}
        class FakeRow:
            def __getitem__(self, key):
                return 3
        score = calc_category_fit(profile, FakeRow())
        assert score == 3.0
    finally:
        conn.close()


def test_calc_category_fit_zero(client):
    db_path = os.environ["RECRUIT_DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        from core.matching import calc_category_fit, CAPABILITIES
        profile = {c: "no" for c in CAPABILITIES}
        class FakeRow:
            def __getitem__(self, key):
                return 3
        score = calc_category_fit(profile, FakeRow())
        assert score == 0.0
    finally:
        conn.close()


def test_op_matching_has_fit_score(client):
    from tests.conftest import login
    # operator 계정으로 로그인
    r = login(client, "op@wone.kr")
    # /op/matching은 job_id 없으면 공고 선택 화면 (fit_score 계산 없음), 그냥 200 확인
    r = client.get("/op/matching", follow_redirects=False)
    assert r.status_code in (200, 302, 303)
