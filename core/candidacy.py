DEFAULT_STAGES = [
    ("reviewing", "검토중"),
    ("shortlisted", "서류합격"),
    ("interview", "면접"),
    ("offer", "제의"),
]

TERMINAL = {"hired", "rejected", "withdrawn"}

STAGE_COLORS = ["primary", "primary", "primary", "primary"]


def get_stages(conn, company_id):
    rows = conn.execute(
        "SELECT stage_key, label FROM company_pipeline_stages WHERE company_id=? ORDER BY sort_order",
        (company_id,),
    ).fetchall()
    if rows:
        return [(r["stage_key"], r["label"]) for r in rows]
    return list(DEFAULT_STAGES)


def get_pipeline_display(conn, company_id):
    stages = get_stages(conn, company_id)
    result = [("pending", "접수", "secondary")]
    for i, (key, label) in enumerate(stages):
        result.append((key, label, STAGE_COLORS[i % len(STAGE_COLORS)]))
    result.append(("hired", "채용", "success"))
    return result


def get_stage_labels(conn, company_id):
    labels = {"pending": "접수", "hired": "채용", "rejected": "불합격", "withdrawn": "지원취소"}
    for key, label in get_stages(conn, company_id):
        labels[key] = label
    return labels


def get_stage_color_map(conn, company_id):
    return {key: color for key, label, color in get_pipeline_display(conn, company_id)}


def get_next_statuses(conn, company_id, current):
    if current in TERMINAL:
        return []
    stages = get_stages(conn, company_id)
    keys = ["pending"] + [s[0] for s in stages] + ["hired"]
    if current not in keys:
        return ["rejected"]
    idx = keys.index(current)
    result = []
    if idx < len(keys) - 1:
        result.append(keys[idx + 1])
    result.append("rejected")
    return result


def can_transition(current, target, conn=None, company_id=None):
    if current in TERMINAL:
        return False
    if conn and company_id:
        return target in get_next_statuses(conn, company_id, current)
    fallback = {
        "pending": ["reviewing", "rejected"],
        "reviewing": ["shortlisted", "rejected"],
        "shortlisted": ["interview", "rejected"],
        "interview": ["offer", "rejected"],
        "offer": ["hired", "rejected"],
    }
    return target in fallback.get(current, [])


def apply_transition(conn, candidacy_id, target, actor_id, comment=""):
    cand = conn.execute("SELECT * FROM candidacies WHERE id=?", (candidacy_id,)).fetchone()
    if not cand:
        return False
    job = conn.execute("SELECT company_id FROM job_postings WHERE id=?", (cand["job_id"],)).fetchone()
    company_id = job["company_id"] if job else None
    current = cand["status"]
    if not can_transition(current, target, conn, company_id):
        return False
    conn.execute(
        "UPDATE candidacies SET status=?, updated_at=datetime('now','localtime') WHERE id=?",
        (target, candidacy_id),
    )
    conn.execute(
        """INSERT INTO status_history (candidacy_id, from_status, to_status, actor_id, comment)
           VALUES (?,?,?,?,?)""",
        (candidacy_id, current, target, actor_id, comment),
    )
    if target == "hired":
        conn.execute(
            """INSERT OR IGNORE INTO placements (candidacy_id, job_id, seeker_user_id, company_id, start_date)
               VALUES (?,?,?,?,date('now','localtime'))""",
            (candidacy_id, cand["job_id"], cand["seeker_user_id"], company_id),
        )
    from core.notifications import create_notification
    labels = get_stage_labels(conn, company_id) if company_id else {}
    label = labels.get(target)
    if label:
        job_row = conn.execute("SELECT title FROM job_postings WHERE id=?", (cand["job_id"],)).fetchone()
        job_title = job_row["title"] if job_row else "공고"
        create_notification(
            conn, cand["seeker_user_id"],
            f"[{job_title}] 지원 상태가 '{label}'(으)로 변경되었습니다.",
            "/applications",
        )
    conn.commit()
    return True
