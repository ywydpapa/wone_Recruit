import json

from core.db import get_sqlite

KINDS = {
    "job": "일자리",
    "apply": "지원",
    "interview": "면접",
    "proposal": "제안",
    "consult": "상담",
    "message": "메시지",
    "system": "시스템",
}

KIND_ICONS = {
    "job": "fa-briefcase",
    "apply": "fa-file-alt",
    "interview": "fa-calendar-check",
    "proposal": "fa-handshake",
    "consult": "fa-headset",
    "message": "fa-envelope",
    "system": "fa-bell",
}

# system 알림은 수신 해제할 수 없음
ROLE_KINDS = {
    "seeker": ["job", "apply", "interview", "proposal", "consult", "message", "system"],
    "company": ["apply", "job", "consult", "message", "system"],
    "manager": ["proposal", "consult", "message", "system"],
    "operator": ["consult", "message", "system"],
}


def create_notification(conn, user_id, message, link="", kind="system"):
    if kind != "system":
        row = conn.execute(
            "SELECT notify_settings FROM users WHERE id=?", (user_id,)
        ).fetchone()
        settings = json.loads(row["notify_settings"])
        if settings.get(kind) is False:
            return
    conn.execute(
        "INSERT INTO notifications (user_id, message, link, kind) VALUES (?,?,?,?)",
        (user_id, message, link, kind),
    )


def get_unread_count(user_id):
    conn = get_sqlite()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",
            (user_id,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()
