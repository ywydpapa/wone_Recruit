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
