import json

CAPABILITIES = [
    "visual_acuity", "hearing", "verbal_comm", "written_comm", "screen_use",
    "reading", "fine_motor", "typing", "upper_mobility", "lower_mobility",
    "lifting", "sitting_endurance", "standing_endurance", "physical_endurance",
    "concentration", "complex_reasoning", "task_switching", "time_management",
    "stress_tolerance", "interpersonal", "work_continuity",
]

_IMPACT_SCORE = {"ok": 3, "at": 2, "limit": 1, "no": 0}
_IMPACT_RANK = {"ok": 0, "at": 1, "limit": 2, "no": 3}

# fit_* 컬럼별 관련 capability 목록
_FIT_CAP_MAP = {
    "fit_visual_low":     ["visual_acuity", "screen_use", "reading"],
    "fit_hearing":        ["hearing", "verbal_comm"],
    "fit_physical_upper": ["fine_motor", "typing", "upper_mobility"],
    "fit_physical_lower": ["lower_mobility", "sitting_endurance", "standing_endurance"],
    "fit_intellectual":   ["concentration", "complex_reasoning", "reading"],
    "fit_autism":         ["concentration", "task_switching", "interpersonal"],
    "fit_mental":         ["stress_tolerance", "task_switching", "interpersonal", "time_management"],
    "fit_internal_organ": ["physical_endurance", "work_continuity"],
    "fit_brain_lesion":   ["fine_motor", "lower_mobility", "sitting_endurance", "concentration"],
}


def build_capability_profile(conn, user_id):
    profile = {cap: "ok" for cap in CAPABILITIES}
    rows = conn.execute(
        """SELECT sic.capability, sic.impact
           FROM seeker_support_items ssi
           JOIN support_item_capabilities sic ON ssi.support_item_id = sic.support_item_id
           WHERE ssi.user_id = ?""",
        (user_id,),
    ).fetchall()
    for row in rows:
        cap = row["capability"] if hasattr(row, "keys") else row[0]
        impact = row["impact"] if hasattr(row, "keys") else row[1]
        if cap in profile and _IMPACT_RANK.get(impact, 0) > _IMPACT_RANK[profile[cap]]:
            profile[cap] = impact
    return profile


def calc_category_fit(capability_profile, job_row):
    total = 0.0
    for fit_col, caps in _FIT_CAP_MAP.items():
        job_score = job_row[fit_col]
        if job_score is None:
            job_score = 3
        scores = [_IMPACT_SCORE[capability_profile.get(c, "ok")] for c in caps]
        seeker_dim = sum(scores) / len(scores)
        total += min(seeker_dim, job_score)
    return round(total / len(_FIT_CAP_MAP), 1)


_SCORE_WEIGHTS = {"fit": 40, "target": 20, "needs": 20, "device": 5, "region": 10, "hours": 5}


def match_score(conn, seeker, job, cat):
    if cat:
        cap_profile = build_capability_profile(conn, seeker["id"])
        fit = calc_category_fit(cap_profile, cat)
    else:
        fit = 3.0
    if fit >= 2:
        fit_label = "적합"
    elif fit >= 1:
        fit_label = "조건부"
    else:
        fit_label = ""

    target_cats = json.loads(seeker["target_categories"])
    target = bool(job["category_id"] and job["category_id"] in target_cats)

    provided = set(json.loads(job["accommodations_provided"])) | set(json.loads(job["accessibility_facilities"]))
    if job["remote_available"] or job["remote_ok"]:
        provided.add("재택근무")
    if job["flexible_hours"] or job["flexible_ok"]:
        provided.add("유연근무")

    needs = json.loads(seeker["accommodation_needs"])
    met = [n for n in needs if n in provided]
    missing = [n for n in needs if n not in provided]
    needs_ratio = len(met) / len(needs) if needs else 1.0

    devices = json.loads(seeker["assistive_tech"])
    device = ("보조기기지원" in provided) if devices else None
    device_ratio = 1 if device or device is None else 0

    region = bool(job["region_sido"] and seeker["region_sido"] == job["region_sido"])
    hours = (seeker["daily_work_hours"] or 8) >= job["min_work_hours"]

    w = _SCORE_WEIGHTS
    score = (
        w["fit"] * (fit / 3)
        + w["target"] * target
        + w["needs"] * needs_ratio
        + w["device"] * device_ratio
        + w["region"] * region
        + w["hours"] * hours
    )

    return {
        "fit": fit, "fit_label": fit_label,
        "target": target,
        "met": met, "missing": missing, "ratio": needs_ratio,
        "device": device,
        "region": region, "hours": hours,
        "score": round(score),
    }
