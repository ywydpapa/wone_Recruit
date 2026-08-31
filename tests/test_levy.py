from core.levy import calc_levy


def _rates():
    return {
        "quota_rate_private": 0.031,
        "levy_per_person_month": 1310000,
        "incentive_min": 350000,
        "incentive_max": 900000,
    }


def test_under_50_no_obligation():
    r = calc_levy(30, 0, _rates())
    assert r["mandatory"] == 0
    assert r["monthly_levy"] == 0


def test_50_plus_mandatory():
    r = calc_levy(100, 2, _rates())
    assert r["mandatory"] == 3  # 100 * 0.031 = 3
    assert r["shortfall"] == 1
    assert r["monthly_levy"] == 1310000


def test_250_employees_3_disabled():
    r = calc_levy(250, 3, _rates())
    assert r["mandatory"] == 7  # 250 * 0.031 = 7
    assert r["shortfall"] == 4
    assert r["monthly_levy"] == 4 * 1310000
    assert r["annual_levy"] == 4 * 1310000 * 12


def test_surplus_incentive():
    r = calc_levy(200, 10, _rates())
    mandatory = 6  # 200 * 0.031
    assert r["mandatory"] == mandatory
    assert r["surplus"] == 4
    assert r["monthly_incentive_min"] == 4 * 350000
    assert r["monthly_incentive_max"] == 4 * 900000


def test_under_100_no_levy():
    r = calc_levy(80, 1, _rates())
    assert r["mandatory"] == 2  # 80 * 0.031
    assert r["shortfall"] == 1
    assert r["levy_applicable"] is False
    assert r["monthly_levy"] == 0


def test_levy_page_renders(client):
    from tests.conftest import login
    login(client, "comp1")
    r = client.get("/company/levy")
    assert r.status_code == 200
    assert "부담금" in r.text
