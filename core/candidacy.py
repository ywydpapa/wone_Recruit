TRANSITIONS = {
    "pending": ["reviewing", "rejected"],
    "reviewing": ["shortlisted", "rejected"],
    "shortlisted": ["interview", "rejected"],
    "interview": ["offer", "rejected"],
    "offer": ["hired", "rejected"],
}

TERMINAL = {"hired", "rejected", "withdrawn"}


def can_transition(current, target):
    if current in TERMINAL:
        return False
    allowed = TRANSITIONS.get(current, [])
    return target in allowed


def apply_transition(conn, candidacy_id, target, actor_id, comment=""):
    cand = conn.execute("SELECT * FROM candidacies WHERE id=?", (candidacy_id,)).fetchone()
    if not cand:
        return False
    current = cand["status"]
    if not can_transition(current, target):
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
               VALUES (?,?,?,
                   (SELECT company_id FROM job_postings WHERE id=?),
                   date('now','localtime'))""",
            (candidacy_id, cand["job_id"], cand["seeker_user_id"], cand["job_id"]),
        )
    # 구직자에게 상태변경 알림
    from core.notifications import create_notification
    _status_labels = {
        "reviewing": "검토중", "shortlisted": "서류합격", "interview": "면접 대상",
        "offer": "합격(제의)", "hired": "최종 채용", "rejected": "불합격",
    }
    if target in _status_labels:
        job = conn.execute("SELECT title FROM job_postings WHERE id=?", (cand["job_id"],)).fetchone()
        job_title = job["title"] if job else "공고"
        create_notification(
            conn, cand["seeker_user_id"],
            f"[{job_title}] 지원 상태가 '{_status_labels[target]}'(으)로 변경되었습니다.",
            "/applications",
        )
    conn.commit()
    return True
