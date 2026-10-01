from datetime import datetime, timedelta


def audience_sql(role):
    if role == "seeker":
        return "(audience='all' OR audience='seeker')"
    if role == "company":
        return "(audience='all' OR audience='company')"
    if role == "manager":
        return "audience='all'"
    return "1=1"


def get_latest(conn, role, limit=3):
    rows = conn.execute(
        f"SELECT * FROM notices WHERE {audience_sql(role)} "
        "ORDER BY pinned DESC, created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    cutoff = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    notices = []
    for r in rows:
        d = dict(r)
        d["new"] = d["created_at"] >= cutoff
        notices.append(d)
    return notices
