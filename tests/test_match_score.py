import json
from core.db import get_sqlite
from core.matching import match_score
from tests.conftest import login


def _seeker(**kw):
    base = dict(
        id=1, target_categories='[]', assistive_tech='[]', accommodation_needs='[]',
        region_sido='서울', daily_work_hours=8,
    )
    base.update(kw)
    return base


def _job(**kw):
    base = dict(
        category_id=None, region_sido='서울', min_work_hours=8,
        accommodations_provided='[]', remote_available=0, flexible_hours=0,
        accessibility_facilities='[]', remote_ok=0, flexible_ok=0,
    )
    base.update(kw)
    return base


def test_target_bonus():
    seeker = _seeker(target_categories=json.dumps([5]))
    hit = match_score(None, seeker, _job(category_id=5), None)
    miss = match_score(None, seeker, _job(category_id=9), None)
    assert hit["target"] is True
    assert miss["target"] is False
    assert hit["score"] > miss["score"]


def test_needs_facility_remote():
    seeker = _seeker(accommodation_needs=json.dumps(["재택근무", "휠체어접근"]))
    job = _job(accessibility_facilities=json.dumps(["휠체어접근"]), remote_ok=1)
    result = match_score(None, seeker, job, None)
    assert set(result["met"]) == {"재택근무", "휠체어접근"}
    assert result["missing"] == []
    assert result["ratio"] == 1.0


def test_needs_coverage_partial():
    seeker = _seeker(accommodation_needs=json.dumps(["재택근무", "엘리베이터"]))
    job = _job()
    result = match_score(None, seeker, job, None)
    assert result["met"] == []
    assert set(result["missing"]) == {"재택근무", "엘리베이터"}
    assert result["ratio"] == 0.0


def test_device_states():
    job = _job(accommodations_provided=json.dumps(["보조기기지원"]))
    no_device = _seeker(assistive_tech='[]')
    assert match_score(None, no_device, job, None)["device"] is None

    with_device = _seeker(assistive_tech=json.dumps(["화면낭독기"]))
    assert match_score(None, with_device, job, None)["device"] is True

    job_no_support = _job()
    assert match_score(None, with_device, job_no_support, None)["device"] is False


def test_score_ordering():
    job = _job(category_id=5, accommodations_provided=json.dumps(["휠체어접근", "보조기기지원"]))
    good = _seeker(
        target_categories=json.dumps([5]),
        accommodation_needs=json.dumps(["휠체어접근"]),
        assistive_tech=json.dumps(["화면낭독기"]),
    )
    bad = _seeker(
        target_categories='[]',
        accommodation_needs=json.dumps(["휠체어접근"]),
        assistive_tech=json.dumps(["화면낭독기"]),
        region_sido='부산',
        daily_work_hours=4,
    )
    good_score = match_score(None, good, job, None)["score"]
    bad_score = match_score(None, bad, job, None)["score"]
    assert good_score > bad_score


def test_matching_route_orders_by_score(client):
    login(client, "counsel1")
    conn = get_sqlite()
    try:
        seeker_id = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
        conn.execute(
            "INSERT INTO manager_assignments (manager_user_id, seeker_user_id, assigned_by) VALUES "
            "((SELECT id FROM users WHERE username='counsel1'), ?, (SELECT id FROM users WHERE username='counsel1'))",
            (seeker_id,),
        )
        conn.commit()
        job_id = conn.execute(
            "SELECT id FROM job_postings WHERE status='open' "
            "AND id NOT IN (SELECT job_id FROM candidacies WHERE seeker_user_id=?) LIMIT 1",
            (seeker_id,),
        ).fetchone()["id"]
    finally:
        conn.close()

    r = client.get(f"/mgr/matching?job_id={job_id}")
    assert r.status_code == 200
    assert "적합도" in r.text


def test_matching_seeker_route(client):
    login(client, "counsel1")
    conn = get_sqlite()
    try:
        manager_id = conn.execute("SELECT id FROM users WHERE username='counsel1'").fetchone()["id"]
        seeker1_id = conn.execute("SELECT id FROM users WHERE username='seeker1'").fetchone()["id"]
        seeker2_id = conn.execute("SELECT id FROM users WHERE username='seeker2'").fetchone()["id"]
        conn.execute(
            "INSERT INTO manager_assignments (manager_user_id, seeker_user_id, assigned_by) VALUES (?,?,?)",
            (manager_id, seeker1_id, manager_id),
        )
        conn.commit()
    finally:
        conn.close()

    r = client.get(f"/mgr/matching/seeker/{seeker1_id}")
    assert r.status_code == 200
    assert "추천 공고" in r.text

    r2 = client.get(f"/mgr/matching/seeker/{seeker2_id}")
    assert r2.status_code == 404
