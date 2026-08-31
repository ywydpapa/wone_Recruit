from core.db import get_sqlite


def _tables(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r["name"] for r in rows}


def test_schema_v2_tables_exist(client):
    conn = get_sqlite()
    expected = {
        "users", "disability_types", "regions", "seeker_profiles", "companies",
        "job_postings", "candidacies", "status_history", "placements",
        "levy_rates", "access_log", "seeker_certifications",
    }
    assert expected <= _tables(conn)
    conn.close()


def test_regions_seeded(client):
    conn = get_sqlite()
    n = conn.execute("SELECT COUNT(*) FROM regions").fetchone()[0]
    sido_count = conn.execute("SELECT COUNT(DISTINCT sido) FROM regions").fetchone()[0]
    conn.close()
    assert n >= 225
    assert sido_count == 16


def test_disability_types_seeded_15(client):
    conn = get_sqlite()
    n = conn.execute("SELECT COUNT(*) FROM disability_types").fetchone()[0]
    conn.close()
    assert n == 15


def test_levy_rates_2026_seeded(client):
    conn = get_sqlite()
    rows = conn.execute("SELECT rate_type, amount FROM levy_rates WHERE year=2026").fetchall()
    conn.close()
    rates = {r["rate_type"]: r["amount"] for r in rows}
    assert rates["quota_rate_private"] == 0.031
    assert rates["levy_per_person_month"] == 1310000
    assert rates["incentive_min"] == 350000
    assert rates["incentive_max"] == 900000


def test_seed_roles(client):
    conn = get_sqlite()
    roles = {
        r["username"]: r["role"]
        for r in conn.execute("SELECT username, role FROM users").fetchall()
    }
    conn.close()
    assert roles["op1"] == "operator"
    assert roles["comp1"] == "company"
    assert roles["seeker1"] == "seeker"
    assert roles["seeker2"] == "seeker"


def test_seed_candidacy_with_history(client):
    conn = get_sqlite()
    cand = conn.execute("SELECT * FROM candidacies").fetchone()
    hist = conn.execute("SELECT COUNT(*) FROM status_history WHERE candidacy_id=?", (cand["id"],)).fetchone()[0]
    conn.close()
    assert cand["source"] == "direct"
    assert cand["status"] == "pending"
    assert hist >= 1
