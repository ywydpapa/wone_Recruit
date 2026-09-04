from core.db import get_sqlite


def create_notification(conn, user_id, message, link=""):
    conn.execute(
        "INSERT INTO notifications (user_id, message, link) VALUES (?,?,?)",
        (user_id, message, link),
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
